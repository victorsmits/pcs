from django.core.management.base import BaseCommand

from providers.models import ProviderEntityMapping


class Command(BaseCommand):
    help = 'Audite les mappings provider vers les objets canoniques.'

    def handle(self, *args, **options):
        total = ProviderEntityMapping.objects.count()
        ambiguous = 0
        orphans = 0
        seen = set()
        for mapping in ProviderEntityMapping.objects.iterator():
            key = (mapping.canonical_model, mapping.canonical_id, mapping.entity_type, mapping.provider_id)
            ambiguous += int(key in seen)
            seen.add(key)
            if not mapping.canonical_model or not mapping.canonical_id:
                orphans += 1
        self.stdout.write(f'mappings={total} duplicate_canonical_links={ambiguous} orphans={orphans}')
