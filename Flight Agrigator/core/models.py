from django.db import models
from django.utils import timezone


class Airport(models.Model):
    iata_code = models.CharField(max_length=3, unique=True, db_index=True)
    city_name = models.CharField(max_length=100)
    airport_name = models.CharField(max_length=200)
    state = models.CharField(max_length=100)
    metro_tier = models.CharField(
        max_length=20,
        choices=[
            ('METRO', 'Metro (Tier-1)'),
            ('TIER_2', 'Tier-2 Major City'),
            ('REGIONAL', 'Regional / UDAN'),
        ],
        default='METRO'
    )

    class Meta:
        ordering = ['iata_code']

    def __str__(self):
        return f"{self.iata_code} - {self.city_name}"


class Route(models.Model):
    origin = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='departing_routes')
    destination = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='arriving_routes')
    route_code = models.CharField(max_length=10, unique=True, db_index=True) # e.g. DEL-BOM
    distance_km = models.PositiveIntegerField(help_text="Flight distance in km")
    dgca_annual_pax = models.BigIntegerField(default=1000000, help_text="Annual passenger traffic reported by DGCA")
    dgca_weight = models.FloatField(default=0.05, help_text="Normalized weight in the national CPI domestic airfare basket")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-dgca_weight']

    def save(self, *args, **kwargs):
        if not self.route_code:
            self.route_code = f"{self.origin.iata_code}-{self.destination.iata_code}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.route_code} (Weight: {self.dgca_weight:.3f})"


class Airline(models.Model):
    code = models.CharField(max_length=5, unique=True) # 6E, AI, IX, SG, QP
    name = models.CharField(max_length=100)
    market_share_pct = models.FloatField(help_text="DGCA Domestic Market Share %")
    is_lcc = models.BooleanField(default=True, help_text="True if Low-Cost Carrier")

    class Meta:
        ordering = ['-market_share_pct']

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.market_share_pct}%"


class FlightQuote(models.Model):
    class SeatClass(models.TextChoices):
        ECONOMY = 'ECONOMY', 'Economy'
        PREMIUM_ECONOMY = 'PREMIUM_ECONOMY', 'Premium Economy'
        BUSINESS = 'BUSINESS', 'Business'

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='quotes', db_index=True)
    airline = models.ForeignKey(Airline, on_delete=models.CASCADE, related_name='quotes', db_index=True)
    flight_number = models.CharField(max_length=20)
    scrape_timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    departure_date = models.DateField(db_index=True)
    departure_time = models.CharField(max_length=10, default="09:00")
    lead_days = models.PositiveSmallIntegerField(
        help_text="Advance booking horizon in days (e.g. 0, 1, 3, 7, 14, 21, 30)",
        db_index=True
    )
    fare_inr = models.FloatField(help_text="Total ticket fare in INR including fuel surcharges and taxes")
    base_fare_inr = models.FloatField(default=0.0)
    fuel_surcharge_inr = models.FloatField(default=0.0)
    tax_fees_inr = models.FloatField(default=0.0)
    stops = models.PositiveSmallIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField(default=120)
    portal_source = models.CharField(max_length=100, default="MakeMyTrip")
    seat_class = models.CharField(max_length=20, choices=SeatClass.choices, default=SeatClass.ECONOMY)
    is_outlier = models.BooleanField(default=False, help_text="Detected as abnormal price surge/drop by IQR filter")
    outlier_reason = models.CharField(max_length=100, blank=True)
    is_cleaned = models.BooleanField(default=True, help_text="Standardized currency and sanitized formats")

    class Meta:
        ordering = ['-scrape_timestamp']
        indexes = [
            models.Index(fields=['route', 'departure_date', 'lead_days']),
            models.Index(fields=['scrape_timestamp', 'airline']),
        ]

    def __str__(self):
        return f"{self.route.route_code} | {self.airline.code} {self.flight_number} | L+{self.lead_days}d: ₹{self.fare_inr:,.0f}"


class AirfarePriceIndex(models.Model):
    class IndexType(models.TextChoices):
        JEVONS = 'JEVONS', 'Jevons Index (Geometric Mean - Recommended)'
        DUTOT = 'DUTOT', 'Dutot Index (Ratio of Arithmetic Means)'
        CARLI = 'CARLI', 'Carli Index (Arithmetic Mean of Price Relatives)'
        TORNQVIST = 'TORNQVIST', 'Törnqvist Multilateral Index'
        FISHER = 'FISHER', 'Fisher Ideal Multilateral Index'

    class LeadStratum(models.TextChoices):
        ALL_WEIGHTED = 'ALL_WEIGHTED', 'All Horizons Composite (Weighted)'
        SAME_DAY_0D = 'SAME_DAY_0D', 'Same-Day Urgent (0 Days)'
        SHORT_1_3D = 'SHORT_1_3D', 'Short Horizon (1-3 Days)'
        MEDIUM_7_14D = 'MEDIUM_7_14D', 'Medium Horizon (7-14 Days)'
        LONG_30D = 'LONG_30D', 'Long Horizon (21-30 Days)'

    index_date = models.DateField(db_index=True)
    index_type = models.CharField(max_length=20, choices=IndexType.choices, default=IndexType.JEVONS)
    lead_stratum = models.CharField(max_length=25, choices=LeadStratum.choices, default=LeadStratum.ALL_WEIGHTED)
    index_value = models.FloatField(help_text="Rebased index value (Base = 100.0)")
    base_period = models.CharField(max_length=50, default="2026-01=100")
    mom_inflation_pct = models.FloatField(null=True, blank=True, help_text="Month-over-Month % change")
    yoy_inflation_pct = models.FloatField(null=True, blank=True, help_text="Year-over-Year % change")
    avg_fare_inr = models.FloatField(help_text="Weighted average airfare on this date")
    sample_size = models.PositiveIntegerField(help_text="Count of price observations aggregated")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-index_date', 'index_type', 'lead_stratum']
        unique_together = ('index_date', 'index_type', 'lead_stratum')

    def __str__(self):
        return f"{self.index_date} | {self.index_type} ({self.lead_stratum}): {self.index_value:.2f}"


class CPITransportBenchmark(models.Model):
    period_month = models.DateField(unique=True, help_text="First day of reference month (YYYY-MM-01)")
    mospi_cpi_general = models.FloatField(help_text="Official MoSPI Headline CPI (Base 2012=100)")
    mospi_cpi_transport = models.FloatField(help_text="Official MoSPI Transport & Communication Sub-index")
    scraped_airfare_index = models.FloatField(help_text="Real-time Airfare Index (Normalized)")
    augmented_cpi_transport = models.FloatField(help_text="Augmented Transport CPI substituting real-time scraped airfares")
    airfare_subgroup_weight = models.FloatField(default=0.032, help_text="Airfare expenditure weight in Transport sub-group")
    inflation_gap_pct = models.FloatField(help_text="Gap between Scraped Airfare inflation and MoSPI delayed survey %")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-period_month']

    def __str__(self):
        return f"{self.period_month.strftime('%b %Y')} | MoSPI Transport: {self.mospi_cpi_transport:.2f} vs Augmented: {self.augmented_cpi_transport:.2f}"


class ScrapeJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        RUNNING = 'RUNNING', 'Running'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    portal = models.CharField(max_length=100, default="Indian Aviation Multi-Portal Aggregator")
    routes_count = models.PositiveIntegerField(default=0)
    quotes_count = models.PositiveIntegerField(default=0)
    duplicates_pruned = models.PositiveIntegerField(default=0)
    outliers_detected = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Job #{self.id} ({self.portal}) - {self.status} [{self.quotes_count} quotes]"


class DataQualityMetrics(models.Model):
    recorded_at = models.DateTimeField(default=timezone.now)
    total_raw_quotes = models.PositiveIntegerField(default=0)
    duplicates_removed = models.PositiveIntegerField(default=0)
    outliers_flagged = models.PositiveIntegerField(default=0)
    clean_records_pct = models.FloatField(default=100.0)
    active_portals = models.CharField(max_length=255, default="MakeMyTrip, Goibibo, Booking.com, Yatra, Cleartrip, IndiGo, Air India")
    data_integrity_status = models.CharField(max_length=50, default="VALIDATED / HIGH QUALITY")

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"Quality Metric {self.recorded_at.strftime('%Y-%m-%d %H:%M')} - {self.clean_records_pct:.1f}% Clean"
