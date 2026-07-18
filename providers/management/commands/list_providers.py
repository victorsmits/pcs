from django.core.management.base import BaseCommand

from providers.models import Provider


class Command(BaseCommand):
    help = 'Liste les providers configurés en base sans les contacter.'

    def handle(self, *args, **options):
        for provider in Provider.objects.order_by('key'):
            enabled = 'enabled' if provider.enabled else 'disabled'
            self.stdout.write(f'{provider.key}\t{enabled}\t{provider.provider_type}\t{provider.health_status}')
