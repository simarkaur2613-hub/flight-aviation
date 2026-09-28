"""
Aviation Econometric Stress-Testing & Shock Transmission Engine.
Simulates macroeconomic shocks to Indian civil aviation and projects their
direct transmission into domestic airfares, the Airfare Price Index (AFPI),
and MoSPI's Consumer Price Index (CPI).

Key Economic Parameters (Indian Market):
- Aviation Turbine Fuel (ATF) share in airline OPEX: ~40% - 44%
- Fuel cost pass-through elasticity: ~0.72 (airlines pass ~72% of fuel surge to spot fares)
- Capacity crunch elasticity: ~1.35 (price elasticity on constrained routes like DEL-BOM)
- Headline CPI Transport weight: 8.59%
- Airfare weight in Transport sub-group: 3.20%
"""

import math
import numpy as np
from core.models import FlightQuote, Route, Airline, AirfarePriceIndex, CPITransportBenchmark
from core.scraper.dgca_data import LEAD_TIME_WEIGHTS


def run_aviation_stress_test(atf_shock_pct=15.0, capacity_crunch_pct=5.0, festive_surge_pct=0.0):
    """
    Simulates macroeconomic and operational shocks:
    - atf_shock_pct: % increase in jet fuel / ATF costs (e.g. +10%, +25%, +50%)
    - capacity_crunch_pct: % reduction in domestic available seat kilometers (e.g. grounded fleet)
    - festive_surge_pct: % additional seasonal travel demand surge (e.g. Diwali peak)
    """
    # 1. Base quotes and parameters
    quotes = FlightQuote.objects.filter(is_outlier=False).select_related('route', 'airline')
    if not quotes.exists():
        return {"status": "error", "message": "No quote observations found."}

    # Pass-through mechanics
    fuel_opex_share = 0.42
    fuel_pass_through_rate = 0.72
    capacity_price_elasticity = 1.35

    # Direct fare shock factor
    # delta_fare_pct = (atf_shock * 0.42 * 0.72) + (capacity_crunch * 1.35) + festive_surge
    fare_inflation_from_atf = (atf_shock_pct / 100.0) * fuel_opex_share * fuel_pass_through_rate
    fare_inflation_from_capacity = (capacity_crunch_pct / 100.0) * capacity_price_elasticity
    fare_inflation_from_festive = festive_surge_pct / 100.0

    total_fare_multiplier = 1.0 + fare_inflation_from_atf + fare_inflation_from_capacity + fare_inflation_from_festive

    # Baseline Jevons
    latest_index_obj = AirfarePriceIndex.objects.filter(
        index_type=AirfarePriceIndex.IndexType.JEVONS,
        lead_stratum=AirfarePriceIndex.LeadStratum.ALL_WEIGHTED
    ).order_by('-index_date').first()

    base_index_val = latest_index_obj.index_value if latest_index_obj else 100.0
    base_avg_fare = latest_index_obj.avg_fare_inr if latest_index_obj else 5800.0

    shocked_index_val = round(base_index_val * total_fare_multiplier, 2)
    shocked_avg_fare = round(base_avg_fare * total_fare_multiplier, 0)
    afpi_change_pct = round(((shocked_index_val / base_index_val) - 1.0) * 100.0, 2)

    # Transmission to MoSPI CPI
    # Airfare expenditure weight in Transport: ~3.2% (0.032)
    airfare_transport_weight = 0.032
    # Transport expenditure weight in Headline CPI: ~8.59% (0.0859)
    transport_headline_weight = 0.0859

    latest_bench = CPITransportBenchmark.objects.order_by('-period_month').first()
    curr_transport_cpi = latest_bench.augmented_cpi_transport if latest_bench else 178.6
    curr_headline_cpi = latest_bench.mospi_cpi_general if latest_bench else 197.1

    # Delta in Transport CPI points
    delta_airfare_index_pts = (shocked_index_val - base_index_val) * (156.8 / 100.0) # scaled to 2012=100
    delta_transport_cpi_pts = round(airfare_transport_weight * delta_airfare_index_pts, 3)
    shocked_transport_cpi = round(curr_transport_cpi + delta_transport_cpi_pts, 2)

    # Delta in Headline CPI points
    delta_headline_cpi_pts = round(transport_headline_weight * delta_transport_cpi_pts, 3)
    shocked_headline_cpi = round(curr_headline_cpi + delta_headline_cpi_pts, 2)

    # Carrier vulnerability ranking
    airlines = Airline.objects.all()
    carrier_impacts = []
    for al in airlines:
        # LCC carriers operate with lower margins, higher fuel pass-through sensitivity
        carrier_sens = 1.12 if al.is_lcc else 0.92
        carrier_shocked_fare = round(base_avg_fare * (1.0 + (total_fare_multiplier - 1.0) * carrier_sens), 0)
        carrier_impacts.append({
            "code": al.code,
            "name": al.name,
            "is_lcc": al.is_lcc,
            "share": al.market_share_pct,
            "shocked_fare": carrier_shocked_fare,
            "fare_surge_pct": round(((carrier_shocked_fare / base_avg_fare) - 1.0) * 100.0, 1),
            "risk_rating": "HIGH VULNERABILITY" if al.is_lcc else "MODERATE BUFFER"
        })

    return {
        "status": "success",
        "inputs": {
            "atf_shock_pct": atf_shock_pct,
            "capacity_crunch_pct": capacity_crunch_pct,
            "festive_surge_pct": festive_surge_pct,
        },
        "airfare_index": {
            "baseline": base_index_val,
            "shocked": shocked_index_val,
            "change_pct": afpi_change_pct,
            "baseline_avg_fare": base_avg_fare,
            "shocked_avg_fare": shocked_avg_fare,
            "fare_difference_inr": shocked_avg_fare - base_avg_fare
        },
        "cpi_transmission": {
            "baseline_transport_cpi": curr_transport_cpi,
            "shocked_transport_cpi": shocked_transport_cpi,
            "delta_transport_pts": delta_transport_cpi_pts,
            "transport_inflation_impact_pct": round((delta_transport_cpi_pts / curr_transport_cpi) * 100.0, 2),
            "baseline_headline_cpi": curr_headline_cpi,
            "shocked_headline_cpi": shocked_headline_cpi,
            "delta_headline_pts": delta_headline_cpi_pts,
        },
        "carrier_impacts": carrier_impacts,
    }
