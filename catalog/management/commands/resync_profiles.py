from django.core.management.base import BaseCommand

from catalog import services


class Command(BaseCommand):
    help = "Upgrade les profils reconstruits depuis l'image en profils vectoriels (cols + altitude)."

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20)
        parser.add_argument('--window', type=int, default=60, help='Fenêtre en jours autour des courses.')

    def handle(self, *args, **opts):
        res = services.resync_image_profiles(limit=opts['limit'], window_days=opts['window'])
        self.stdout.write(self.style.SUCCESS(
            f"{res['upgraded']}/{res['checked']} profil(s) upgradé(s) en vectoriel."))
