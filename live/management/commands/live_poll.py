from django.core.management.base import BaseCommand

from live import services
from live.models import LiveSession


class Command(BaseCommand):
    help = 'Poll (synchrone) toutes les sessions live actives, une fois. Utile sans worker.'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Inclure aussi les sessions inactives.')

    def handle(self, *args, **opts):
        qs = LiveSession.objects.select_related('stage__race')
        if not opts['all']:
            qs = qs.filter(is_active=True)
        n = 0
        for session in qs:
            res = services.sync_live_session(session.stage, force=True)
            status = res.race_status if res else 'échec'
            self.stdout.write(f'  {session.stage} → {status}')
            n += 1
        self.stdout.write(self.style.SUCCESS(f'{n} session(s) pollée(s).'))
