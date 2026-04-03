"""
Management command to sync cycling data from PCS.
Usage:
    python manage.py sync_data                          # full sync (all years, all types)
    python manage.py sync_data --years 2025 2026        # specific years
    python manage.py sync_data --type races             # only races
    python manage.py sync_data --type results           # only race results
    python manage.py sync_data --type riders            # only top-500 riders + rankings
    python manage.py sync_data --type rosters           # only team rosters
    python manage.py sync_data --type nationalities     # nationality + current_team fill
"""
import logging
from datetime import date
from django.core.management.base import BaseCommand
from django.core.cache import cache
from core.services import pcs_reset_session

logger = logging.getLogger(__name__)

YEARS = [2024, 2025, 2026]


class Command(BaseCommand):
    help = 'Synchronise les donnees depuis procyclingstats.com'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type', type=str, default='all',
            choices=['all', 'races', 'teams', 'results', 'riders', 'rosters', 'nationalities'],
            help='Type de donnees a synchroniser'
        )
        parser.add_argument('--years', nargs='+', type=int, default=YEARS,
                            help='Annees a synchroniser (ex: 2024 2025 2026)')
        parser.add_argument('--no-cache', action='store_true', help='Vider le cache avant sync')

    def handle(self, *args, **options):
        sync_type = options['type']
        years = options['years']

        if options['no_cache']:
            cache.clear()
            pcs_reset_session()
            self.stdout.write('Cache vide.')

        self.stdout.write(self.style.SUCCESS(
            f'[SYNC] type={sync_type}  annees={years}'
        ))

        if sync_type in ('all', 'races'):
            self._sync_races(years)

        if sync_type in ('all', 'teams'):
            self._sync_teams(years)

        if sync_type in ('all', 'riders'):
            self._sync_riders_rankings()

        if sync_type in ('all', 'results'):
            self._sync_results(years)

        if sync_type in ('all', 'rosters'):
            self._sync_rosters(years)

        if sync_type in ('all', 'nationalities'):
            self._sync_nationalities()
            self._link_current_teams()

        self.stdout.write(self.style.SUCCESS('[OK] Synchronisation terminee !'))
        self._print_summary()

    # ------------------------------------------------------------------ #

    def _sync_races(self, years):
        from races.services import fetch_races_by_year
        from races.models import Race
        self.stdout.write('  Courses...')
        for year in years:
            fetch_races_by_year(year)
        total = Race.objects.filter(year__in=years).count()
        self.stdout.write(self.style.SUCCESS(f'    {total} courses'))

    def _sync_teams(self, years):
        from teams.services import fetch_teams_by_year
        from teams.models import Team
        self.stdout.write('  Equipes...')
        for year in years:
            fetch_teams_by_year(year)
        total = Team.objects.filter(year__in=years).count()
        self.stdout.write(self.style.SUCCESS(f'    {total} equipes'))

    def _sync_riders_rankings(self):
        from riders.models import Rider
        from rankings.models import RiderRanking
        from core.services import pcs_get
        self.stdout.write('  Coureurs top-500 + classements...')
        saved = 0
        for offset in range(0, 500, 100):
            url = f'https://www.procyclingstats.com/rankings.php?s=season-individual&offset={offset}'
            soup = pcs_get(url)
            if not soup:
                break
            table = soup.find('table', class_='basic')
            if not table:
                break
            rows = table.select('tbody tr')
            if not rows:
                break
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 5:
                    continue
                rank_text = cols[0].get_text(strip=True)
                rank = int(rank_text) if rank_text.isdigit() else None
                flag = cols[3].find('span', class_='flag')
                nat = ''
                if flag:
                    cls = flag.get('class', [])
                    nat = cls[1].upper() if len(cls) > 1 else ''
                rider_link = cols[3].find('a', href=lambda h: h and 'rider/' in h)
                if not rider_link:
                    continue
                slug = rider_link.get('href', '').lstrip('/')[6:]
                name = rider_link.get_text(strip=True)
                pts_text = cols[5].get_text(strip=True) if len(cols) > 5 else '0'
                pts = int(pts_text) if pts_text.isdigit() else 0
                rider, _ = Rider.objects.update_or_create(
                    slug=slug,
                    defaults={'name': name, 'nationality': nat, 'pcs_rank': rank}
                )
                RiderRanking.objects.update_or_create(
                    rider=rider, year=2026, ranking_type='pcs',
                    defaults={'rank': rank, 'points': pts}
                )
                saved += 1
        self.stdout.write(self.style.SUCCESS(f'    {saved} coureurs / classements'))

    def _sync_results(self, years=None):
        from races.services import fetch_race_detail
        from races.models import Race
        from riders.models import RaceResult
        today = date.today()
        qs = Race.objects.filter(end_date__lte=today)
        if years:
            qs = qs.filter(year__in=years)
        completed = list(qs.order_by('year', 'end_date'))
        self.stdout.write(f'  Resultats ({len(completed)} courses terminees)...')
        ok = err = 0
        for race in completed:
            try:
                fetch_race_detail(race.slug, race.year)
                ok += 1
                if ok % 25 == 0:
                    self.stdout.write(
                        f'    {ok}/{len(completed)} courses — {RaceResult.objects.count()} resultats'
                    )
            except Exception as exc:
                err += 1
                logger.debug('results ERR %s %d: %s', race.slug, race.year, exc)
        total = RaceResult.objects.count()
        self.stdout.write(self.style.SUCCESS(f'    {total} resultats ({ok} ok / {err} err)'))

    def _sync_rosters(self, years):
        from teams.services import fetch_team_detail
        from teams.models import Team
        self.stdout.write('  Effectifs...')
        saved = 0
        qs = Team.objects.filter(year__in=years, status__in=['WorldTeam', 'ProTeam'])
        for team in qs:
            try:
                fetch_team_detail(team.slug, team.year)
                saved += 1
            except Exception as exc:
                logger.debug('roster ERR %s %d: %s', team.slug, team.year, exc)
        self.stdout.write(self.style.SUCCESS(f'    {saved} equipes avec effectif'))

    def _sync_nationalities(self):
        from riders.models import Rider
        from core.services import pcs_get
        self.stdout.write('  Nationalites...')
        updated = 0
        for offset in range(0, 600, 100):
            url = f'https://www.procyclingstats.com/rankings.php?s=season-individual&offset={offset}'
            soup = pcs_get(url)
            if not soup:
                break
            table = soup.find('table', class_='basic')
            if not table:
                break
            rows = table.select('tbody tr')
            if not rows:
                break
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 4:
                    continue
                flag = cols[3].find('span', class_='flag')
                if not flag:
                    continue
                cls = flag.get('class', [])
                nat = cls[1].upper() if len(cls) > 1 else ''
                rider_link = cols[3].find('a', href=lambda h: h and 'rider/' in h)
                if not rider_link or not nat:
                    continue
                slug = rider_link.get('href', '').lstrip('/')[6:]
                updated += Rider.objects.filter(slug=slug, nationality='').update(nationality=nat)
        # also fill from race results flags (already done during _sync_results)
        self.stdout.write(self.style.SUCCESS(
            f'    {updated} coureurs mis a jour  —  '
            f'{Rider.objects.filter(nationality="").count()} encore vides'
        ))

    def _link_current_teams(self):
        from riders.models import Rider, RaceResult
        self.stdout.write('  Liaison coureurs -> equipes...')
        updated = 0
        batch = []
        for rider in Rider.objects.filter(current_team=None).iterator(chunk_size=500):
            res = (RaceResult.objects
                   .filter(rider=rider, team__isnull=False)
                   .order_by('-year', '-race__end_date')
                   .select_related('team')
                   .first())
            if res:
                rider.current_team = res.team
                batch.append(rider)
            if len(batch) >= 500:
                Rider.objects.bulk_update(batch, ['current_team'])
                updated += len(batch)
                batch = []
        if batch:
            Rider.objects.bulk_update(batch, ['current_team'])
            updated += len(batch)
        self.stdout.write(self.style.SUCCESS(f'    {updated} coureurs lies a une equipe'))

    def _print_summary(self):
        from races.models import Race
        from teams.models import Team
        from riders.models import Rider, RaceResult
        from rankings.models import RiderRanking
        self.stdout.write('')
        self.stdout.write('=== RESUME BASE DE DONNEES ===')
        self.stdout.write(f'  Courses       : {Race.objects.count()}')
        self.stdout.write(f'  Equipes       : {Team.objects.count()}')
        self.stdout.write(f'  Coureurs      : {Rider.objects.count()}')
        self.stdout.write(f'  Resultats     : {RaceResult.objects.count()}')
        self.stdout.write(f'  Classements   : {RiderRanking.objects.count()}')
