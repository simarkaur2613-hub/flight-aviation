from django.core.management.base import BaseCommand
from core.scraper.data_seeder import seed_reference_data, seed_historical_flight_quotes
from core.econometric.index_calculator import run_airfare_index_pipeline
from core.econometric.cpi_augmenter import update_cpi_augmentation_benchmarks


class Command(BaseCommand):
    help = 'Seeds DGCA Indian aviation reference data, historical fare quotes, and computes indices.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--months',
            type=int,
            default=6,
            help='Number of historical months of flight quotes to seed'
        )

    def handle(self, *args, **options):
        months = options.get('months', 6)
        self.stdout.write(self.style.SUCCESS("Starting DGCA reference data seeding..."))
        seed_reference_data()

        self.stdout.write(self.style.SUCCESS(f"Seeding historical flight quotes ({months} months)..."))
        seed_historical_flight_quotes(months_back=months)

        self.stdout.write(self.style.SUCCESS("Running econometric index pipeline (Jevons, Dutot, Carli, Fisher, Törnqvist)..."))
        res = run_airfare_index_pipeline()
        self.stdout.write(self.style.SUCCESS(f"Index pipeline result: {res}"))

        self.stdout.write(self.style.SUCCESS("Augmenting MoSPI CPI Transport benchmarks..."))
        bench_res = update_cpi_augmentation_benchmarks()
        self.stdout.write(self.style.SUCCESS(f"CPI Augmentation result: {bench_res}"))

        self.stdout.write(self.style.SUCCESS("Setup and initialization completed successfully!"))
