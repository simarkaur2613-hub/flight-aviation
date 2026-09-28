import json
import csv
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import models
from django.db.models import Avg, Min, Max, Count, Q
from django.utils import timezone
from core.models import (
    Airport, Route, Airline, FlightQuote,
    AirfarePriceIndex, CPITransportBenchmark, ScrapeJob, DataQualityMetrics
)
from core.scraper.collector import AirfareScraperEngine
from core.econometric.index_calculator import run_airfare_index_pipeline
from core.econometric.cpi_augmenter import update_cpi_augmentation_benchmarks
from core.scraper.dgca_data import LEAD_TIME_WEIGHTS


def dashboard_view(request):
    """Main executive dashboard tracking real-time airfare index and CPI augmentation."""
    # Latest index values
    latest_index = AirfarePriceIndex.objects.filter(
        index_type=AirfarePriceIndex.IndexType.JEVONS,
        lead_stratum=AirfarePriceIndex.LeadStratum.ALL_WEIGHTED
    ).order_by('-index_date').first()

    # Time series of composite Jevons indices
    indices_qs = AirfarePriceIndex.objects.filter(
        index_type=AirfarePriceIndex.IndexType.JEVONS,
        lead_stratum=AirfarePriceIndex.LeadStratum.ALL_WEIGHTED
    ).order_by('index_date')

    # Lead stratum breakdown series
    strata_series = {}
    for stratum_choice in AirfarePriceIndex.LeadStratum.choices:
        s_code = stratum_choice[0]
        if s_code == AirfarePriceIndex.LeadStratum.ALL_WEIGHTED:
            continue
        series_data = list(AirfarePriceIndex.objects.filter(
            index_type=AirfarePriceIndex.IndexType.JEVONS,
            lead_stratum=s_code
        ).order_by('index_date').values('index_date', 'index_value', 'avg_fare_inr'))
        strata_series[s_code] = {
            "label": stratum_choice[1],
            "data": [{"date": str(x['index_date']), "val": x['index_value'], "fare": x['avg_fare_inr']} for x in series_data]
        }

    # CPI benchmark data
    cpi_benchmarks = list(CPITransportBenchmark.objects.order_by('period_month').values(
        'period_month', 'mospi_cpi_general', 'mospi_cpi_transport',
        'scraped_airfare_index', 'augmented_cpi_transport', 'inflation_gap_pct'
    ))

    # Summary KPIs
    total_quotes = FlightQuote.objects.count()
    active_routes = Route.objects.filter(is_active=True).count()
    latest_benchmark = CPITransportBenchmark.objects.order_by('-period_month').first()

    # Airline stats
    airlines = Airline.objects.all().order_by('-market_share_pct')
    airline_avg_fares = []
    for al in airlines:
        avg_f = FlightQuote.objects.filter(airline=al).aggregate(avg=Avg('fare_inr'))['avg'] or 0.0
        airline_avg_fares.append({
            "name": al.name,
            "code": al.code,
            "share": al.market_share_pct,
            "is_lcc": al.is_lcc,
            "avg_fare": round(avg_f, 0)
        })

    # Prepare chart payloads as JSON for template
    time_series_data = [
        {
            "date": str(x.index_date),
            "jevons": x.index_value,
            "mom": x.mom_inflation_pct or 0.0,
            "fare": x.avg_fare_inr,
            "sample": x.sample_size,
        }
        for x in indices_qs
    ]

    cpi_chart_data = [
        {
            "month": x['period_month'].strftime('%b %Y'),
            "mospi_transport": x['mospi_cpi_transport'],
            "augmented_transport": x['augmented_cpi_transport'],
            "scraped_airfare": x['scraped_airfare_index'],
            "inflation_gap": x['inflation_gap_pct']
        }
        for x in cpi_benchmarks
    ]

    context = {
        "latest_index": latest_index,
        "latest_benchmark": latest_benchmark,
        "total_quotes": total_quotes,
        "active_routes": active_routes,
        "time_series_json": json.dumps(time_series_data),
        "strata_series_json": json.dumps(strata_series),
        "cpi_chart_json": json.dumps(cpi_chart_data),
        "airline_stats": airline_avg_fares,
        "last_updated": timezone.now(),
    }
    return render(request, "dashboard.html", context)


def methodology_view(request):
    """Detailed view explaining and comparing Jevons, Dutot, Carli, Fisher, and Törnqvist indices."""
    dates = AirfarePriceIndex.objects.values_list('index_date', flat=True).distinct().order_by('index_date')
    
    formula_comparison = []
    for d in dates:
        row = {"date": str(d)}
        records = AirfarePriceIndex.objects.filter(
            index_date=d,
            lead_stratum=AirfarePriceIndex.LeadStratum.ALL_WEIGHTED
        )
        for r in records:
            row[r.index_type.lower()] = r.index_value
        formula_comparison.append(row)

    routes = Route.objects.filter(is_active=True).select_related('origin', 'destination').order_by('-dgca_weight')
    
    context = {
        "formula_data_json": json.dumps(formula_comparison),
        "routes": routes,
        "lead_weights": LEAD_TIME_WEIGHTS,
    }
    return render(request, "methodology.html", context)


def routes_view(request):
    """Advance booking curves and route-level price dispersion explorer."""
    routes = Route.objects.filter(is_active=True).select_related('origin', 'destination').order_by('route_code')
    selected_route_code = request.GET.get('route', 'DEL-BOM')
    selected_route = Route.objects.filter(route_code=selected_route_code).first() or routes.first()

    # Dynamic pricing curve across lead horizons for selected route
    lead_curve = []
    if selected_route:
        lead_agg = FlightQuote.objects.filter(route=selected_route).values('lead_days').annotate(
            avg_fare=Avg('fare_inr'),
            min_fare=Min('fare_inr'),
            max_fare=Max('fare_inr'),
            count=Count('id')
        ).order_by('lead_days')
        for item in lead_agg:
            lead_curve.append({
                "lead_days": item['lead_days'],
                "avg_fare": round(item['avg_fare'], 0),
                "min_fare": round(item['min_fare'], 0),
                "max_fare": round(item['max_fare'], 0),
                "count": item['count'],
            })

    # Airline breakdown on selected route
    carrier_breakdown = []
    if selected_route:
        carrier_agg = FlightQuote.objects.filter(route=selected_route).values(
            'airline__name', 'airline__code', 'airline__is_lcc'
        ).annotate(
            avg_fare=Avg('fare_inr'),
            min_fare=Min('fare_inr'),
            count=Count('id')
        ).order_by('avg_fare')
        for item in carrier_agg:
            carrier_breakdown.append({
                "name": item['airline__name'],
                "code": item['airline__code'],
                "is_lcc": item['airline__is_lcc'],
                "avg_fare": round(item['avg_fare'], 0),
                "min_fare": round(item['min_fare'], 0),
                "count": item['count'],
            })

    context = {
        "routes": routes,
        "selected_route": selected_route,
        "lead_curve_json": json.dumps(lead_curve),
        "carrier_breakdown": carrier_breakdown,
    }
    return render(request, "routes.html", context)


def scraper_view(request):
    """Scraper console to monitor jobs, trigger on-demand scraping, and inspect microdata."""
    recent_jobs = ScrapeJob.objects.order_by('-created_at')[:15]
    recent_quotes = FlightQuote.objects.select_related('route', 'airline').order_by('-scrape_timestamp')[:30]

    context = {
        "recent_jobs": recent_jobs,
        "recent_quotes": recent_quotes,
        "total_quotes": FlightQuote.objects.count(),
        "total_jobs": ScrapeJob.objects.count(),
    }
    return render(request, "scraper.html", context)


@require_POST
def trigger_scrape_view(request):
    """Trigger an on-demand live scraping cycle and recalculate indices."""
    engine = AirfareScraperEngine(portal_name="On-Demand Web Console Scraper")
    job = engine.run_live_scrape_cycle()

    if job.status == ScrapeJob.Status.COMPLETED:
        # Re-run index calculations and update CPI benchmarks
        run_airfare_index_pipeline()
        update_cpi_augmentation_benchmarks()
        messages.success(request, f"Scrape cycle completed: {job.quotes_count} quotes harvested. CPI indices updated!")
    else:
        messages.error(request, f"Scraper finished with issue: {job.details}")

    return redirect("scraper")


@require_POST
def recalculate_indices_view(request):
    """Manually re-run the econometric index estimation pipeline."""
    res = run_airfare_index_pipeline()
    update_cpi_augmentation_benchmarks()
    messages.success(request, f"Econometric pipeline recalculation complete. Processed {res.get('dates_processed', 0)} periods.")
    return redirect("dashboard")


# REST API & Export Endpoints
def api_indices(request):
    """JSON API endpoint returning calculated price index time-series."""
    index_type = request.GET.get('type', 'JEVONS')
    stratum = request.GET.get('stratum', 'ALL_WEIGHTED')
    
    qs = AirfarePriceIndex.objects.filter(
        index_type=index_type,
        lead_stratum=stratum
    ).order_by('index_date')

    data = [
        {
            "date": str(x.index_date),
            "index_value": x.index_value,
            "mom_inflation_pct": x.mom_inflation_pct,
            "avg_fare_inr": x.avg_fare_inr,
            "sample_size": x.sample_size,
        }
        for x in qs
    ]
    return JsonResponse({"status": "success", "count": len(data), "index_type": index_type, "stratum": stratum, "data": data})


def api_cpi_benchmark(request):
    """JSON API endpoint returning MoSPI official vs Scraped augmented CPI data."""
    benchmarks = CPITransportBenchmark.objects.order_by('period_month')
    data = [
        {
            "period": x.period_month.strftime('%Y-%m'),
            "mospi_cpi_general": x.mospi_cpi_general,
            "mospi_cpi_transport": x.mospi_cpi_transport,
            "scraped_airfare_index": x.scraped_airfare_index,
            "augmented_cpi_transport": x.augmented_cpi_transport,
            "inflation_gap_pct": x.inflation_gap_pct,
        }
        for x in benchmarks
    ]
    return JsonResponse({"status": "success", "data": data})


def validation_view(request):
    """Data Quality, Cleaning & Reliability Assurance View (Polarchy SIH Steps 03 & 07)."""
    from core.scraper.cleaner import clean_and_validate_quotes

    # Run check if none exists
    latest_metric = DataQualityMetrics.objects.order_by('-recorded_at').first()
    if not latest_metric:
        clean_res = clean_and_validate_quotes()
        latest_metric = DataQualityMetrics.objects.order_by('-recorded_at').first()

    # Outliers sample
    flagged_outliers = FlightQuote.objects.filter(is_outlier=True).select_related('route', 'airline')[:20]

    # Portal distribution
    portal_distribution = FlightQuote.objects.values('portal_source').annotate(
        total_quotes=Count('id'),
        avg_fare=Avg('fare_inr'),
        outliers=Count('id', filter=models.Q(is_outlier=True))
    ).order_by('-total_quotes')

    context = {
        "latest_metric": latest_metric,
        "flagged_outliers": flagged_outliers,
        "portal_distribution": portal_distribution,
        "total_quotes": FlightQuote.objects.count(),
        "clean_quotes": FlightQuote.objects.filter(is_outlier=False).count(),
        "outlier_count": FlightQuote.objects.filter(is_outlier=True).count(),
    }
    return render(request, "validation.html", context)


def policy_report_view(request):
    """Print-ready Executive Policy Brief for MoSPI, DGCA, and SIH26056 Evaluators."""
    latest_index = AirfarePriceIndex.objects.filter(
        index_type=AirfarePriceIndex.IndexType.JEVONS,
        lead_stratum=AirfarePriceIndex.LeadStratum.ALL_WEIGHTED
    ).order_by('-index_date').first()

    benchmarks = CPITransportBenchmark.objects.order_by('-period_month')[:6]
    routes = Route.objects.filter(is_active=True).order_by('-dgca_weight')[:10]
    airlines = Airline.objects.all().order_by('-market_share_pct')

    context = {
        "team_name": "Polarchy",
        "problem_id": "SIH26056",
        "title": "Development of a Real-time Airfare Price Index for India through Automated Web Scraping for Augmentation of the CPI",
        "latest_index": latest_index,
        "benchmarks": benchmarks,
        "top_routes": routes,
        "airlines": airlines,
        "report_date": timezone.localdate(),
    }
    return render(request, "policy_report.html", context)


# REST API & Export Endpoints
def api_cpi_simulate(request):
    """
    Dynamic CPI Augmentation Simulator API (Step 05 & 06).
    Accepts customized airfare subgroup weight and returns dynamic augmented CPI trajectory.
    """
    try:
        custom_weight = float(request.GET.get('weight', 0.032))
    except (ValueError, TypeError):
        custom_weight = 0.032

    # Clamp weight between 0.005 (0.5%) and 0.15 (15%)
    custom_weight = max(0.005, min(0.15, custom_weight))

    benchmarks = CPITransportBenchmark.objects.order_by('period_month')
    results = []

    for b in benchmarks:
        official_transport = b.mospi_cpi_transport
        official_airfare = 152.0 + (official_transport - 169.5) * 1.05
        scraped_airfare = b.scraped_airfare_index

        sim_augmented = (
            official_transport
            - (custom_weight * official_airfare)
            + (custom_weight * scraped_airfare)
        )
        gap = round(sim_augmented - official_transport, 2)

        results.append({
            "period": b.period_month.strftime('%b %Y'),
            "official_transport": round(official_transport, 2),
            "scraped_airfare": round(scraped_airfare, 2),
            "simulated_augmented": round(sim_augmented, 2),
            "inflation_divergence_pts": gap
        })

    return JsonResponse({
        "status": "success",
        "custom_weight": custom_weight,
        "weight_pct": round(custom_weight * 100, 2),
        "data": results
    })


def api_validation_stats(request):
    """JSON API endpoint returning data quality and cleaning metrics."""
    latest = DataQualityMetrics.objects.order_by('-recorded_at').first()
    data = {
        "status": "success",
        "total_quotes": latest.total_raw_quotes if latest else 0,
        "duplicates_removed": latest.duplicates_removed if latest else 0,
        "outliers_flagged": latest.outliers_flagged if latest else 0,
        "clean_records_pct": latest.clean_records_pct if latest else 100.0,
        "integrity_status": latest.data_integrity_status if latest else "VALIDATED",
    }
    return JsonResponse(data)


def stress_test_view(request):
    """Aviation Fuel & Capacity Crunch Stress-Testing Simulator (Corporate / Central Bank Tool)."""
    from core.econometric.stress_tester import run_aviation_stress_test
    
    # Default 15% ATF shock, 5% capacity crunch
    sim_result = run_aviation_stress_test(atf_shock_pct=15.0, capacity_crunch_pct=5.0, festive_surge_pct=0.0)

    context = {
        "sim_result": sim_result,
        "sim_result_json": json.dumps(sim_result),
    }
    return render(request, "stress_test.html", context)


def hedonic_view(request):
    """Hedonic Quality-Adjustment Econometric Regression Studio (ONS / Eurostat CPI Model)."""
    from core.econometric.hedonic import run_hedonic_regression

    reg_result = run_hedonic_regression()
    context = {
        "reg_result": reg_result,
    }
    return render(request, "hedonic.html", context)


def api_stress_test(request):
    """JSON API endpoint returning live recalculated aviation shock transmission."""
    from core.econometric.stress_tester import run_aviation_stress_test

    try:
        atf = float(request.GET.get('atf', 15.0))
        capacity = float(request.GET.get('capacity', 5.0))
        festive = float(request.GET.get('festive', 0.0))
    except (ValueError, TypeError):
        atf, capacity, festive = 15.0, 5.0, 0.0

    result = run_aviation_stress_test(atf_shock_pct=atf, capacity_crunch_pct=capacity, festive_surge_pct=festive)
    return JsonResponse(result)


def export_quotes_csv(request):
    """Download flight quotes microdata as CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="scraped_airfare_microdata_{timezone.localdate()}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Quote ID', 'Route Code', 'Origin', 'Destination', 'Airline Code', 'Airline Name',
        'Flight Number', 'Portal Source', 'Scrape Timestamp', 'Departure Date', 'Lead Days', 'Total Fare INR',
        'Base Fare INR', 'Fuel Surcharge INR', 'Tax and Fees INR', 'Is Outlier', 'Duration Minutes'
    ])

    quotes = FlightQuote.objects.select_related('route__origin', 'route__destination', 'airline').order_by('-scrape_timestamp')[:5000]
    for q in quotes:
        writer.writerow([
            q.id, q.route.route_code, q.route.origin.iata_code, q.route.destination.iata_code,
            q.airline.code, q.airline.name, q.flight_number, q.portal_source, q.scrape_timestamp.isoformat(),
            q.departure_date.isoformat(), q.lead_days, q.fare_inr, q.base_fare_inr,
            q.fuel_surcharge_inr, q.tax_fees_inr, q.is_outlier, q.duration_minutes
        ])
    return response
