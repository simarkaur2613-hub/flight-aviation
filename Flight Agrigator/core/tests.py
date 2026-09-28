import datetime
import numpy as np
from django.test import TestCase, Client
from django.urls import reverse
from core.models import Airport, Route, Airline, FlightQuote, AirfarePriceIndex, CPITransportBenchmark, ScrapeJob
from core.econometric.index_calculator import compute_elementary_indices, classify_lead_stratum, run_airfare_index_pipeline
from core.econometric.cpi_augmenter import update_cpi_augmentation_benchmarks
from core.scraper.collector import AirfareScraperEngine
from core.scraper.data_seeder import seed_reference_data


class EconometricIndexMathTests(TestCase):
    def test_elementary_index_axioms(self):
        """Tests axiomatic mathematical properties: Carli >= Jevons (Jensen's inequality)."""
        base_fares = [3000, 4000, 5000, 6000]
        # Prices increase heterogeneously
        curr_fares = [3600, 4400, 6000, 6600]

        jevons, dutot, carli = compute_elementary_indices(curr_fares, base_fares)

        self.assertGreater(jevons, 1.0)
        self.assertGreater(dutot, 1.0)
        # Fundamental theorem of price index formulas: Carli >= Jevons
        self.assertGreaterEqual(carli, jevons)

    def test_lead_stratum_classification(self):
        self.assertEqual(classify_lead_stratum(0), "SAME_DAY_0D")
        self.assertEqual(classify_lead_stratum(1), "SHORT_1_3D")
        self.assertEqual(classify_lead_stratum(3), "SHORT_1_3D")
        self.assertEqual(classify_lead_stratum(7), "MEDIUM_7_14D")
        self.assertEqual(classify_lead_stratum(14), "MEDIUM_7_14D")
        self.assertEqual(classify_lead_stratum(30), "LONG_30D")


class PipelineAndViewsIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_reference_data()

    def test_route_weights_sum_to_one(self):
        """Verifies that normalized DGCA passenger weights across active routes sum to ~1.0."""
        routes = Route.objects.filter(is_active=True)
        total_weight = sum(r.dgca_weight for r in routes)
        self.assertAlmostEqual(total_weight, 1.0, places=2)

    def test_live_scraper_cycle(self):
        """Tests that scraper execution saves quotes and records a completed ScrapeJob."""
        engine = AirfareScraperEngine(portal_name="Test Engine")
        # Run on top 2 routes for fast test
        routes = Route.objects.filter(is_active=True)[:2]
        job = engine.run_live_scrape_cycle(target_routes=routes, lead_horizons=(0, 7, 30))

        self.assertEqual(job.status, ScrapeJob.Status.COMPLETED)
        self.assertGreater(job.quotes_count, 0)
        self.assertTrue(FlightQuote.objects.exists())

    def test_index_calculation_and_cpi_augmentation(self):
        """Tests index pipeline and CPI augmentation after quote creation."""
        engine = AirfareScraperEngine(portal_name="Test Engine")
        routes = Route.objects.filter(is_active=True)[:2]
        engine.run_live_scrape_cycle(target_routes=routes, lead_horizons=(0, 7, 30))

        # Run pipeline
        res = run_airfare_index_pipeline()
        self.assertEqual(res["status"], "success")
        self.assertTrue(AirfarePriceIndex.objects.exists())

        # Run CPI augmentation
        cpi_res = update_cpi_augmentation_benchmarks()
        self.assertEqual(cpi_res["status"], "success")
        self.assertTrue(CPITransportBenchmark.objects.exists())

    def test_clean_and_validate_quotes(self):
        """Tests Polarchy data cleaning, deduplication, and outlier detection (Steps 03 & 07)."""
        from core.scraper.cleaner import clean_and_validate_quotes
        engine = AirfareScraperEngine(portal_name="Test Engine")
        routes = Route.objects.filter(is_active=True)[:2]
        engine.run_live_scrape_cycle(target_routes=routes, lead_horizons=(0, 7, 30))

        res = clean_and_validate_quotes()
        self.assertEqual(res["status"], "success")
        self.assertGreater(res["total_raw"], 0)
        self.assertGreaterEqual(res["clean_pct"], 0.0)

    def test_cpi_simulate_api(self):
        """Tests interactive CPI simulation API endpoint with custom weight."""
        engine = AirfareScraperEngine(portal_name="Test Engine")
        routes = Route.objects.filter(is_active=True)[:2]
        engine.run_live_scrape_cycle(target_routes=routes, lead_horizons=(0, 7, 30))
        run_airfare_index_pipeline()
        update_cpi_augmentation_benchmarks()

        response = self.client.get(reverse('api_cpi_simulate') + '?weight=0.05')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["weight_pct"], 5.0)
        self.assertGreater(len(data["data"]), 0)

    def test_stress_test_and_hedonic_engines(self):
        """Tests aviation stress testing and hedonic regression engines."""
        from core.econometric.stress_tester import run_aviation_stress_test
        from core.econometric.hedonic import run_hedonic_regression

        engine = AirfareScraperEngine(portal_name="Test Engine")
        routes = Route.objects.filter(is_active=True)[:2]
        engine.run_live_scrape_cycle(target_routes=routes, lead_horizons=(0, 7, 30))
        run_airfare_index_pipeline()

        stress_res = run_aviation_stress_test(atf_shock_pct=20.0, capacity_crunch_pct=10.0)
        self.assertEqual(stress_res["status"], "success")
        self.assertGreater(stress_res["airfare_index"]["shocked"], stress_res["airfare_index"]["baseline"])

        hedonic_res = run_hedonic_regression()
        self.assertEqual(hedonic_res["status"], "success")
        self.assertGreaterEqual(hedonic_res["r_squared"], 0.0)

    def test_all_views_return_200(self):
        """Ensures all web pages and API endpoints return HTTP 200 OK."""
        # Seed test quotes & run index
        engine = AirfareScraperEngine()
        routes = Route.objects.filter(is_active=True)[:2]
        engine.run_live_scrape_cycle(target_routes=routes, lead_horizons=(0, 7, 30))
        run_airfare_index_pipeline()
        update_cpi_augmentation_benchmarks()

        # Check endpoints
        urls = [
            reverse('dashboard'),
            reverse('stress_test'),
            reverse('hedonic'),
            reverse('methodology'),
            reverse('routes'),
            reverse('scraper'),
            reverse('validation'),
            reverse('policy_report'),
            reverse('api_indices'),
            reverse('api_cpi_benchmark'),
            reverse('api_cpi_simulate'),
            reverse('api_stress_test'),
            reverse('api_validation_stats'),
            reverse('export_quotes_csv'),
        ]
        for u in urls:
            response = self.client.get(u)
            self.assertEqual(response.status_code, 200, f"URL {u} failed with status {response.status_code}")
