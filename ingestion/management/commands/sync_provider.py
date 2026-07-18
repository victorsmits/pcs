from django.core.management.base import BaseCommand, CommandError

from providers.capabilities import ProviderCapability
from providers.models import Provider

from ingestion.orchestrator import IngestionOrchestrator


class Command(BaseCommand):
    help = 'Synchronise un provider enregistré via le moteur ingestion canonique.'

    def add_arguments(self, parser):
        parser.add_argument('--provider', required=True)
        parser.add_argument('--capability', default=ProviderCapability.CALENDAR.value, choices=[c.value for c in ProviderCapability])
        parser.add_argument('--year', type=int)

    def handle(self, *args, **options):
        try:
            Provider.objects.get(key=options['provider'], enabled=True)
        except Provider.DoesNotExist as exc:
            raise CommandError('Provider inconnu ou désactivé') from exc
        try:
            run = IngestionOrchestrator().sync_provider_capability(
                provider_key=options['provider'], capability=ProviderCapability(options['capability']), query={'year': options['year']}
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f'run={run.public_id} status={run.status} received={run.records_received} created={run.records_created} updated={run.records_updated} conflicts={run.conflicts_created}'
        ))
