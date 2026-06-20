from django.conf import settings
from django.core.management.base import BaseCommand

from catalog import services


class Command(BaseCommand):
    help = 'Synchronise le calendrier PCS pour une ou plusieurs années.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=None)
        parser.add_argument('--circuits', nargs='+', default=None,
                            help='Clés de circuit : wt pro wwt')

    def handle(self, *args, **opts):
        year = opts['year'] or settings.CURRENT_SEASON
        total = services.sync_calendar(year, opts['circuits'])
        self.stdout.write(self.style.SUCCESS(f'{total} courses synchronisées pour {year}.'))
