"""
Management command to sync cycling data from PCS.
Usage:
    python manage.py sync_data --year 2024 --type all
    python manage.py sync_data --year 2024 --type races
    python manage.py sync_data --type riders --slugs tadej-pogacar remco-evenepoel
    python manage.py sync_data --year 2024 --type teams
"""
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Synchronise les données depuis procyclingstats.com'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=2024, help='Année à synchroniser')
        parser.add_argument(
            '--type', type=str, default='all',
            choices=['all', 'races', 'teams', 'riders', 'rankings'],
            help='Type de données à synchroniser'
        )
        parser.add_argument('--slugs', nargs='+', help='Slugs spécifiques à synchroniser')
        parser.add_argument('--gender', type=str, default='M', choices=['M', 'F'], help='Genre (M/F)')

    def handle(self, *args, **options):
        year = options['year']
        sync_type = options['type']
        slugs = options.get('slugs', [])
        gender = options['gender']

        self.stdout.write(self.style.SUCCESS(f'🚴 Synchronisation des données {sync_type} pour {year}...'))

        if sync_type in ('all', 'races'):
            self._sync_races(year)

        if sync_type in ('all', 'teams'):
            self._sync_teams(year, gender)

        if sync_type in ('all', 'riders') and slugs:
            self._sync_riders(slugs)

        if sync_type == 'riders' and not slugs:
            self.stdout.write(self.style.WARNING('Précisez --slugs pour synchroniser des coureurs spécifiques.'))

        self.stdout.write(self.style.SUCCESS('✅ Synchronisation terminée !'))

    def _sync_races(self, year):
        from races.services import fetch_races_by_year
        self.stdout.write(f'  → Courses {year}...')
        try:
            races = fetch_races_by_year(year)
            count = races.count() if hasattr(races, 'count') else len(races)
            self.stdout.write(self.style.SUCCESS(f'     {count} courses synchronisées'))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'     Erreur: {exc}'))

    def _sync_teams(self, year, gender):
        from teams.services import fetch_teams_by_year
        self.stdout.write(f'  → Équipes {year} ({gender})...')
        try:
            teams = fetch_teams_by_year(year, gender)
            count = teams.count() if hasattr(teams, 'count') else len(teams)
            self.stdout.write(self.style.SUCCESS(f'     {count} équipes synchronisées'))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'     Erreur: {exc}'))

    def _sync_riders(self, slugs):
        from riders.services import fetch_rider_from_pcs
        self.stdout.write(f'  → {len(slugs)} coureur(s)...')
        success = 0
        for slug in slugs:
            try:
                rider = fetch_rider_from_pcs(slug)
                if rider:
                    self.stdout.write(f'     ✓ {rider.name}')
                    success += 1
                else:
                    self.stdout.write(self.style.WARNING(f'     ✗ {slug} introuvable'))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'     ✗ {slug}: {exc}'))
        self.stdout.write(self.style.SUCCESS(f'     {success}/{len(slugs)} coureurs synchronisés'))
