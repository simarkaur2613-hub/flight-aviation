"""
Data Seeder for Indian Aviation CPI Augmentation.
Populates Airports, Airlines, DGCA Routes, and multi-month calibrated time-series quotes
to empower immediate econometric index estimation, advance booking analysis, and MoSPI benchmarking.
"""

import datetime
import random
from django.utils import timezone
from core.models import Airport, Airline, Route, FlightQuote, CPITransportBenchmark
from core.scraper.dgca_data import AIRPORTS_DATA, AIRLINES_DATA, ROUTES_DATA, MOSPI_BASELINE_RECORDS
from core.scraper.collector import AirfareScraperEngine


def seed_reference_data():
    """Seeds master reference tables: Airports, Airlines, and Routes with DGCA passenger weights."""
    print("Seeding Airports...")
    airports = {}
    for ap in AIRPORTS_DATA:
        obj, created = Airport.objects.update_or_create(
            iata_code=ap["iata"],
            defaults={
                "city_name": ap["city"],
                "airport_name": ap["name"],
                "state": ap["state"],
                "metro_tier": ap["tier"],
            }
        )
        airports[ap["iata"]] = obj

    print("Seeding Airlines...")
    airlines = {}
    for al in AIRLINES_DATA:
        obj, created = Airline.objects.update_or_create(
            code=al["code"],
            defaults={
                "name": al["name"],
                "market_share_pct": al["market_share_pct"],
                "is_lcc": al["is_lcc"],
            }
        )
        airlines[al["code"]] = obj

    print("Seeding Routes & DGCA Passenger Weights...")
    total_pax = sum(r["pax"] for r in ROUTES_DATA)
    for r in ROUTES_DATA:
        orig = airports.get(r["orig"])
        dest = airports.get(r["dest"])
        if orig and dest:
            weight = r["pax"] / total_pax
            Route.objects.update_or_create(
                route_code=f"{r['orig']}-{r['dest']}",
                defaults={
                    "origin": orig,
                    "destination": dest,
                    "distance_km": r["dist"],
                    "dgca_annual_pax": r["pax"],
                    "dgca_weight": round(weight, 5),
                    "is_active": True,
                }
            )

    print("Seeding MoSPI Baseline Benchmarks...")
    for rec in MOSPI_BASELINE_RECORDS:
        p_date = datetime.date.fromisoformat(rec["month"])
        # Initial estimated augmented CPI
        CPITransportBenchmark.objects.update_or_create(
            period_month=p_date,
            defaults={
                "mospi_cpi_general": rec["cpi_general"],
                "mospi_cpi_transport": rec["cpi_transport"],
                "scraped_airfare_index": 100.0,
                "augmented_cpi_transport": rec["cpi_transport"],
                "inflation_gap_pct": 0.0,
                "notes": "MoSPI Official Reference Series"
            }
        )
    print("Master reference tables seeded successfully.")


def seed_historical_flight_quotes(months_back=6, quotes_per_month_sample=150):
    """
    Generates historical time-series microdata quotes across the previous months
    incorporating empirical Indian seasonality trends (Diwali, Summer holidays, Aviation turbine fuel shifts).
    """
    print(f"Generating historical time series for the past {months_back} months...")
    routes = list(Route.objects.filter(is_active=True))
    airlines = list(Airline.objects.all())
    
    if not routes or not airlines:
        seed_reference_data()
        routes = list(Route.objects.filter(is_active=True))
        airlines = list(Airline.objects.all())

    engine = AirfareScraperEngine(portal_name="Historical Multi-Portal Archive")
    quotes_to_insert = []
    
    today = timezone.localdate()
    
    # Lead days horizons: 0 (same day), 1, 3, 7, 14, 30
    horizons = [0, 1, 3, 7, 14, 30]

    # Create monthly historical sample points
    for m in range(months_back, -1, -1):
        # Sample date in middle of each month
        month_offset_days = m * 30
        sample_scrape_date = today - datetime.timedelta(days=month_offset_days)
        
        # Monthly macroeconomic inflation drift factor (e.g. ATF price variations)
        # Higher in festive months (Oct-Nov) and summer rush (May-June)
        month_num = sample_scrape_date.month
        seasonality = 1.15 if month_num in [10, 11, 12] else (1.09 if month_num in [5, 6] else 1.0)
        trend = 1.0 + (months_back - m) * 0.008  # gradual ~0.8% monthly inflation trend
        
        # Take key routes
        for route in routes[:10]:
            for airline in airlines:
                for lead in horizons:
                    dep_date = sample_scrape_date + datetime.timedelta(days=lead)
                    q = engine.fetch_live_quote(route, airline, lead, dep_date)
                    
                    # Apply historical monthly inflation & seasonality adjustment
                    adj_factor = seasonality * trend
                    q["fare_inr"] = round(q["fare_inr"] * adj_factor, -1)
                    q["base_fare_inr"] = round(q["base_fare_inr"] * adj_factor, -1)
                    q["scrape_timestamp"] = timezone.make_aware(
                        datetime.datetime.combine(sample_scrape_date, datetime.time(9, 30))
                    )
                    quotes_to_insert.append(FlightQuote(**q))

    # Bulk insert
    FlightQuote.objects.bulk_create(quotes_to_insert)
    print(f"Generated {len(quotes_to_insert)} historical quotes across {months_back} months.")
