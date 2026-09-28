from django.core.management.base import BaseCommand
from core.scraper.collector import AirfareScraperEngine
from core.econometric.index_calculator import run_airfare_index_pipeline
from core.econometric.cpi_augmenter import update_cpi_augmentation_benchmarks


class Command(BaseCommand):
    help = 'Executes an automated scraping cycle for Indian domestic flights and updates price index.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Executing automated flight quote scraping cycle..."))
        engine = AirfareScraperEngine(portal_name="Automated Scheduled CLI Scraper")
        job = engine.run_live_scrape_cycle()

        self.stdout.write(self.style.SUCCESS(
            f"Scrape Job finished with status '{job.status}'. Routes: {job.routes_count}, Quotes: {job.quotes_count}"
        ))

        self.stdout.write(self.style.NOTICE("Updating econometric price indices..."))
        index_res = run_airfare_index_pipeline()
        self.stdout.write(self.style.SUCCESS(f"Indices updated: {index_res}"))

        self.stdout.write(self.style.NOTICE("Updating CPI Transport benchmarks..."))
        cpi_res = update_cpi_augmentation_benchmarks()
        self.stdout.write(self.style.SUCCESS(f"CPI benchmarks updated: {cpi_res}"))
