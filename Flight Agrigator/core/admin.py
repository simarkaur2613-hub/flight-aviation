from django.contrib import admin
from core.models import (
    Airport, Route, Airline, FlightQuote,
    AirfarePriceIndex, CPITransportBenchmark, ScrapeJob, DataQualityMetrics
)


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ('iata_code', 'city_name', 'airport_name', 'state', 'metro_tier')
    list_filter = ('metro_tier', 'state')
    search_fields = ('iata_code', 'city_name', 'airport_name')


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('route_code', 'origin', 'destination', 'distance_km', 'dgca_annual_pax', 'dgca_weight', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('route_code', 'origin__city_name', 'destination__city_name')
    ordering = ('-dgca_weight',)


@admin.register(Airline)
class AirlineAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'market_share_pct', 'is_lcc')
    list_filter = ('is_lcc',)
    search_fields = ('code', 'name')
    ordering = ('-market_share_pct',)


@admin.register(FlightQuote)
class FlightQuoteAdmin(admin.ModelAdmin):
    list_display = ('route', 'airline', 'flight_number', 'departure_date', 'lead_days', 'fare_inr', 'portal_source', 'scrape_timestamp')
    list_filter = ('airline', 'lead_days', 'route', 'seat_class')
    search_fields = ('flight_number', 'route__route_code')
    date_hierarchy = 'scrape_timestamp'
    readonly_fields = ('scrape_timestamp',)


@admin.register(AirfarePriceIndex)
class AirfarePriceIndexAdmin(admin.ModelAdmin):
    list_display = ('index_date', 'index_type', 'lead_stratum', 'index_value', 'mom_inflation_pct', 'avg_fare_inr', 'sample_size')
    list_filter = ('index_type', 'lead_stratum')
    date_hierarchy = 'index_date'
    ordering = ('-index_date', 'index_type')


@admin.register(CPITransportBenchmark)
class CPITransportBenchmarkAdmin(admin.ModelAdmin):
    list_display = ('period_month', 'mospi_cpi_general', 'mospi_cpi_transport', 'scraped_airfare_index', 'augmented_cpi_transport', 'inflation_gap_pct')
    date_hierarchy = 'period_month'
    ordering = ('-period_month',)


@admin.register(ScrapeJob)
class ScrapeJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'portal', 'status', 'routes_count', 'quotes_count', 'duplicates_pruned', 'outliers_detected', 'created_at', 'completed_at')
    list_filter = ('status', 'portal')
    readonly_fields = ('created_at', 'completed_at')


@admin.register(DataQualityMetrics)
class DataQualityMetricsAdmin(admin.ModelAdmin):
    list_display = ('recorded_at', 'clean_records_pct', 'duplicates_removed', 'outliers_flagged', 'data_integrity_status')
    readonly_fields = ('recorded_at',)
