from django.core.management.base import BaseCommand, CommandError

from providers.models import Provider


class Command(BaseCommand):
    help = "Affiche l'état connu d'un provider sans le contacter automatiquement."

    def add_arguments(self, parser):
        parser.add_argument('--provider', required=True)

    def handle(self, *args, **options):
        try:
            provider = Provider.objects.get(key=options['provider'])
        except Provider.DoesNotExist as exc:
            raise CommandError('provider not found') from exc
        self.stdout.write(f'{provider.key}: {provider.health_status}')
        if provider.last_error:
            self.stdout.write(provider.last_error)
