"""
CPI Augmentation and Policy Analytics Module.
Calculates the impact of replacing traditional manual periodic airfare survey quotes
with high-frequency scraped microdata on MoSPI's Consumer Price Index (CPI) Transport & Communication group.
"""

import datetime
from django.utils import timezone
from core.models import CPITransportBenchmark, AirfarePriceIndex
from core.scraper.dgca_data import MOSPI_BASELINE_RECORDS

# Airfare expenditure share within the Transport and Communication subgroup in Indian CPI basket
AIRFARE_SUBGROUP_WEIGHT = 0.032  # 3.2% of Transport sub-index


def update_cpi_augmentation_benchmarks():
    """
    Recalculates CPI benchmarks with real-time scraped airfare index data.
    Quantifies the measurement gap between official delayed surveys and real-time scraped indexes.
    """
    # Get computed composite Jevons indices
    jevons_records = AirfarePriceIndex.objects.filter(
        index_type=AirfarePriceIndex.IndexType.JEVONS,
        lead_stratum=AirfarePriceIndex.LeadStratum.ALL_WEIGHTED
    ).order_by('index_date')

    if not jevons_records.exists():
        return {"status": "warning", "message": "No airfare price index records available. Run index pipeline first."}

    # Map dates to index values
    index_map = {rec.index_date: rec.index_value for rec in jevons_records}
    available_dates = sorted(index_map.keys())

    # Reference base factor (to match 2012=100 scaling around ~156.8 for Jan 2026)
    base_official_airfare = 156.8

    updated_count = 0
    for benchmark in CPITransportBenchmark.objects.all():
        b_date = benchmark.period_month
        
        # Find closest scraped index date
        closest_date = min(available_dates, key=lambda d: abs((d - b_date).days))
        scraped_rebased_val = index_map[closest_date]

        # Convert our 100-base scraped index to MoSPI 2012=100 scale
        scaled_scraped_airfare = (scraped_rebased_val / 100.0) * base_official_airfare
        benchmark.scraped_airfare_index = round(scaled_scraped_airfare, 2)

        # Baseline official transport index
        official_transport = benchmark.mospi_cpi_transport
        
        # Approximate official airfare component in the baseline
        official_airfare_component = 152.0 + (official_transport - 169.5) * 1.05

        # Substitute official slow airfare with high-frequency dynamic scraped index
        # CPI_Augmented = CPI_Transport_Official - w_air * Official_Air + w_air * Scraped_Air
        augmented_transport = (
            official_transport
            - (AIRFARE_SUBGROUP_WEIGHT * official_airfare_component)
            + (AIRFARE_SUBGROUP_WEIGHT * scaled_scraped_airfare)
        )

        benchmark.augmented_cpi_transport = round(augmented_transport, 2)
        
        # Inflation measurement divergence (gap in percentage points)
        official_yoy_proxy = ((official_airfare_component / 152.0) - 1.0) * 100.0
        scraped_yoy_proxy = ((scaled_scraped_airfare / base_official_airfare) - 1.0) * 100.0
        benchmark.inflation_gap_pct = round(scraped_yoy_proxy - official_yoy_proxy, 2)
        benchmark.airfare_subgroup_weight = AIRFARE_SUBGROUP_WEIGHT
        benchmark.notes = f"Mapped to scrape date {closest_date} (Index={scraped_rebased_val:.1f})"
        benchmark.save()
        updated_count += 1

    return {
        "status": "success",
        "benchmarks_updated": updated_count,
        "subgroup_weight": AIRFARE_SUBGROUP_WEIGHT,
    }
