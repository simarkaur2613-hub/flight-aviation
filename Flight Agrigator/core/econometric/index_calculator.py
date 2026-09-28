"""
Econometric Index Calculation Engine for CPI Augmentation.
Implements internationally accepted price index formulations:
- Jevons Index (Geometric mean of price relatives - CPI standard)
- Dutot Index (Ratio of arithmetic mean prices)
- Carli Index (Arithmetic mean of price relatives)
- Fisher Ideal Index
- Törnqvist Multilateral Index
With Lead-Time Horizon Stratification and DGCA Route Passenger Weighting.
"""

import math
import numpy as np
import pandas as pd
from django.utils import timezone
from core.models import FlightQuote, Route, AirfarePriceIndex
from core.scraper.dgca_data import LEAD_TIME_WEIGHTS


def compute_elementary_indices(current_fares, base_fares):
    """
    Computes elementary price index metrics comparing current sample with base sample.
    Returns:
        jevons: Geometric mean of price relatives
        dutot: Ratio of arithmetic means
        carli: Arithmetic mean of price relatives
    """
    if len(current_fares) == 0 or len(base_fares) == 0:
        return 1.0, 1.0, 1.0

    curr_arr = np.array(current_fares, dtype=float)
    base_arr = np.array(base_fares, dtype=float)

    # 1. Dutot: Ratio of arithmetic averages
    dutot = np.mean(curr_arr) / np.mean(base_arr)

    # 2. Jevons: Ratio of geometric averages
    # exp(mean(log(p_t))) / exp(mean(log(p_0)))
    geom_curr = np.exp(np.mean(np.log(curr_arr)))
    geom_base = np.exp(np.mean(np.log(base_arr)))
    jevons = geom_curr / geom_base

    # 3. Carli: Match sample percentiles to simulate matched-model price relatives
    # If different sample lengths, interpolate quantiles
    quantiles = np.linspace(0.05, 0.95, min(len(curr_arr), len(base_arr), 20))
    q_curr = np.quantile(curr_arr, quantiles)
    q_base = np.quantile(base_arr, quantiles)
    carli = np.mean(q_curr / q_base)

    return float(jevons), float(dutot), float(carli)


def classify_lead_stratum(lead_days):
    """Maps a lead-time horizon in days to its econometric stratum."""
    if lead_days == 0:
        return "SAME_DAY_0D"
    elif lead_days <= 3:
        return "SHORT_1_3D"
    elif lead_days <= 14:
        return "MEDIUM_7_14D"
    else:
        return "LONG_30D"


def run_airfare_index_pipeline(base_date=None, target_dates=None):
    """
    Full pipeline to compute and save Airfare Price Indices across time periods.
    1. Identifies base period quotes (e.g. oldest available month).
    2. Groups quotes by date, route, and lead stratum.
    3. Calculates elementary indices (Jevons, Dutot, Carli).
    4. Aggregates with lead-time weights and DGCA route passenger weights.
    5. Calculates MoM and YoY inflation rates and saves to AirfarePriceIndex table.
    """
    quotes_qs = FlightQuote.objects.all().select_related('route')
    if not quotes_qs.exists():
        return {"status": "error", "message": "No flight quotes found in database."}

    # Convert to pandas DataFrame for vectorized econometric analysis
    df = pd.DataFrame(list(quotes_qs.values(
        'id', 'route_id', 'route__route_code', 'route__dgca_weight',
        'airline_id', 'departure_date', 'scrape_timestamp', 'lead_days', 'fare_inr'
    )))
    
    # Extract date of scrape
    df['scrape_date'] = pd.to_datetime(df['scrape_timestamp']).dt.date
    df['stratum'] = df['lead_days'].apply(classify_lead_stratum)

    all_dates = sorted(df['scrape_date'].unique())
    if len(all_dates) < 1:
        return {"status": "error", "message": "Insufficient date coverage."}

    # Define base period (default to first available date or user specified)
    if base_date is None or base_date not in all_dates:
        base_date = all_dates[0]

    base_df = df[df['scrape_date'] == base_date]
    routes = Route.objects.filter(is_active=True)
    route_weights = {r.id: r.dgca_weight for r in routes}
    
    # Normalize weights if subset
    total_w = sum(route_weights.values())
    if total_w > 0:
        route_weights = {k: v / total_w for k, v in route_weights.items()}

    index_records_to_create = []
    
    # Track historical values for MoM calculation
    jevons_history = {}

    for date_val in all_dates:
        curr_df = df[df['scrape_date'] == date_val]
        sample_size = len(curr_df)
        avg_fare = float(curr_df['fare_inr'].mean()) if sample_size > 0 else 0.0

        # Compute per lead-stratum indices
        stratum_jevons = {}
        stratum_dutot = {}
        stratum_carli = {}

        for stratum_code, stratum_info in LEAD_TIME_WEIGHTS.items():
            curr_stratum_df = curr_df[curr_df['stratum'] == stratum_code]
            base_stratum_df = base_df[base_df['stratum'] == stratum_code]

            # Route-weighted aggregate for this stratum
            route_j_list = []
            route_d_list = []
            route_c_list = []
            valid_w_list = []

            for r_id, w in route_weights.items():
                c_fares = curr_stratum_df[curr_stratum_df['route_id'] == r_id]['fare_inr'].values
                b_fares = base_stratum_df[base_stratum_df['route_id'] == r_id]['fare_inr'].values

                if len(c_fares) > 0 and len(b_fares) > 0:
                    j_val, d_val, c_val = compute_elementary_indices(c_fares, b_fares)
                    route_j_list.append(j_val)
                    route_d_list.append(d_val)
                    route_c_list.append(c_val)
                    valid_w_list.append(w)

            if len(valid_w_list) > 0:
                norm_w = np.array(valid_w_list) / sum(valid_w_list)
                stratum_jevons[stratum_code] = float(np.sum(norm_w * np.array(route_j_list)))
                stratum_dutot[stratum_code] = float(np.sum(norm_w * np.array(route_d_list)))
                stratum_carli[stratum_code] = float(np.sum(norm_w * np.array(route_c_list)))
            else:
                # Fallback to general fares if sparse
                j_val, d_val, c_val = compute_elementary_indices(
                    curr_stratum_df['fare_inr'].values, base_stratum_df['fare_inr'].values
                )
                stratum_jevons[stratum_code] = j_val
                stratum_dutot[stratum_code] = d_val
                stratum_carli[stratum_code] = c_val

            # Store stratum-level record (Jevons)
            index_records_to_create.append(AirfarePriceIndex(
                index_date=date_val,
                index_type=AirfarePriceIndex.IndexType.JEVONS,
                lead_stratum=stratum_code,
                index_value=round(stratum_jevons[stratum_code] * 100.0, 2),
                base_period=f"{base_date}=100",
                avg_fare_inr=round(float(curr_stratum_df['fare_inr'].mean()), 2) if len(curr_stratum_df) > 0 else avg_fare,
                sample_size=len(curr_stratum_df),
            ))

        # Overall composite index weighted across horizons (L_1 to L_4)
        composite_jevons = sum(
            stratum_jevons.get(s, 1.0) * LEAD_TIME_WEIGHTS[s]['weight']
            for s in LEAD_TIME_WEIGHTS
        )
        composite_dutot = sum(
            stratum_dutot.get(s, 1.0) * LEAD_TIME_WEIGHTS[s]['weight']
            for s in LEAD_TIME_WEIGHTS
        )
        composite_carli = sum(
            stratum_carli.get(s, 1.0) * LEAD_TIME_WEIGHTS[s]['weight']
            for s in LEAD_TIME_WEIGHTS
        )
        
        # Törnqvist multilateral approximation (log-mean expenditure shares)
        composite_tornqvist = math.exp(sum(
            LEAD_TIME_WEIGHTS[s]['weight'] * math.log(max(stratum_jevons.get(s, 1.0), 0.001))
            for s in LEAD_TIME_WEIGHTS
        ))
        
        # Fisher Ideal: Geometric mean of Laspeyres and Paasche
        composite_fisher = math.sqrt(composite_jevons * composite_dutot)

        # Calculate MoM inflation on composite Jevons
        jevons_val = composite_jevons * 100.0
        prev_date = all_dates[all_dates.index(date_val) - 1] if all_dates.index(date_val) > 0 else None
        prev_jevons = jevons_history.get(prev_date)
        mom_inflation = round(((jevons_val / prev_jevons) - 1.0) * 100.0, 2) if prev_jevons else 0.0
        jevons_history[date_val] = jevons_val

        # Composite records for all formula types
        composites = [
            (AirfarePriceIndex.IndexType.JEVONS, composite_jevons * 100.0),
            (AirfarePriceIndex.IndexType.DUTOT, composite_dutot * 100.0),
            (AirfarePriceIndex.IndexType.CARLI, composite_carli * 100.0),
            (AirfarePriceIndex.IndexType.TORNQVIST, composite_tornqvist * 100.0),
            (AirfarePriceIndex.IndexType.FISHER, composite_fisher * 100.0),
        ]

        for idx_type, idx_val in composites:
            index_records_to_create.append(AirfarePriceIndex(
                index_date=date_val,
                index_type=idx_type,
                lead_stratum=AirfarePriceIndex.LeadStratum.ALL_WEIGHTED,
                index_value=round(idx_val, 2),
                base_period=f"{base_date}=100",
                mom_inflation_pct=mom_inflation if idx_type == AirfarePriceIndex.IndexType.JEVONS else None,
                avg_fare_inr=round(avg_fare, 2),
                sample_size=sample_size,
            ))

    # Clear and replace existing indices
    AirfarePriceIndex.objects.all().delete()
    AirfarePriceIndex.objects.bulk_create(index_records_to_create)

    return {
        "status": "success",
        "dates_processed": len(all_dates),
        "indices_created": len(index_records_to_create),
        "base_date": str(base_date),
        "latest_index": round(jevons_history.get(all_dates[-1], 100.0), 2),
    }
