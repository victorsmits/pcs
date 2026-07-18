from django.core.management.base import BaseCommand, CommandError

from catalog.seed_services import seed_national_championships


class Command(BaseCommand):
    help = 'Seed idempotent des championnats nationaux route/ITT ME/WE pour les pays P1/P2.'

    def handle(self, *args, **options):
        try:
            result = seed_national_championships()
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f'created={result.created} updated={result.updated} aliases_created={result.aliases_created} aliases_updated={result.aliases_updated}'
        ))
