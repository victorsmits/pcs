from django.core.management.base import BaseCommand

from ingestion.models import DataConflict


class Command(BaseCommand):
    help = 'Liste les conflits de données provider en attente.'

    def add_arguments(self, parser):
        parser.add_argument('--status', default='open')

    def handle(self, *args, **options):
        conflicts = DataConflict.objects.filter(status=options['status']).order_by('-created_at')
        for conflict in conflicts:
            self.stdout.write(f'{conflict.public_id} {conflict.entity_type}.{conflict.field_name} {conflict.reason}')
        self.stdout.write(f'{conflicts.count()} conflict(s)')
