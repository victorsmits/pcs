from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog.seed_services import DEFAULT_ROAD_SERIES_PATH, seed_road_series


class Command(BaseCommand):
    help = 'Seed idempotent des séries route déclarées dans catalog/seeds/road_series.yaml.'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DEFAULT_ROAD_SERIES_PATH))

    def handle(self, *args, **options):
        try:
            result = seed_road_series(Path(options['file']))
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f'created={result.created} updated={result.updated} aliases_created={result.aliases_created} aliases_updated={result.aliases_updated}'
        ))
