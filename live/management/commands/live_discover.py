from django.core.management.base import BaseCommand

from live import services


class Command(BaseCommand):
    help = 'Détecte les étapes live du jour depuis PCS et active les sessions.'

    def handle(self, *args, **opts):
        result = services.discover_live_today()
        self.stdout.write(self.style.SUCCESS(
            f"Sessions actives : {result['active']} (étapes créées : {result['created']})"))
