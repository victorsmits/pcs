import logging
import threading
import uuid
from datetime import date

from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from cycling.models import Race, RaceResult, Rider, Stage, StartEntry, Team
from cycling.scraper import (
    find_ongoing_races,
    sync_race,
    sync_races_year,
    sync_rankings,
    sync_stage_results,
    sync_stages,
    sync_team,
)

logger = logging.getLogger(__name__)

SYNC_TYPES = [
    ('races', 'Courses'),
    ('teams', 'Équipes'),
    ('results', 'Résultats'),
    ('riders', 'Coureurs'),
    ('rosters', 'Effectifs'),
    ('all', 'Tout'),
]


def home(request):
    today = date.today()
    current_year = today.year

    recent_races = Race.objects.filter(
        end_date__lte=today, year=current_year
    ).order_by('-end_date')[:6]

    upcoming_races = Race.objects.filter(
        start_date__gt=today
    ).order_by('start_date')[:6]

    ongoing_races = find_ongoing_races()[:3]

    top_riders = Rider.objects.filter(
        is_active=True, pcs_rank__isnull=False
    ).order_by('pcs_rank')[:10]

    stats = {
        'total_riders': Rider.objects.filter(is_active=True).count(),
        'total_races': Race.objects.filter(year=current_year).count(),
        'total_teams': Team.objects.filter(year=current_year).count(),
    }

    return render(request, 'cycling/home.html', {
        'recent_races': recent_races,
        'upcoming_races': upcoming_races,
        'ongoing_races': ongoing_races,
        'top_riders': top_riders,
        'stats': stats,
    })


def race_list(request):
    current_year = date.today().year
    year = int(request.GET.get('year', current_year))
    classification = request.GET.get('classification', '')
    q = request.GET.get('q', '')
    race_type = request.GET.get('type', 'all')

    races = Race.objects.filter(year=year).order_by('start_date')

    if classification:
        races = races.filter(classification=classification)
    if q:
        races = races.filter(name__icontains=q)
    if race_type == 'stage':
        races = races.filter(is_stage_race=True, is_grand_tour=False)
    elif race_type == 'oneday':
        races = races.filter(is_stage_race=False)
    elif race_type == 'grand_tour':
        races = races.filter(is_grand_tour=True)
    elif race_type == 'monument':
        races = races.filter(is_monument=True)

    paginator = Paginator(races, 40)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'cycling/race_list.html', {
        'page_obj': page,
        'year': year,
        'years_available': range(current_year + 1, 2019, -1),
        'classification': classification,
        'q': q,
        'race_type': race_type,
    })


def race_detail(request, slug, year):
    race = get_object_or_404(Race, slug=slug, year=year)

    if request.GET.get('refresh') == '1':
        try:
            sync_race(slug, year)
            sync_stages(race)
        except Exception:
            logger.exception('Refresh failed for %s %s', slug, year)

    is_live = race.is_live

    gc_results = RaceResult.objects.filter(
        race=race, result_type='gc', stage__isnull=True
    ).select_related('rider', 'team').order_by('rank')[:50]

    points_results = RaceResult.objects.filter(
        race=race, result_type='points', stage__isnull=True
    ).select_related('rider', 'team').order_by('rank')[:30]

    kom_results = RaceResult.objects.filter(
        race=race, result_type='kom', stage__isnull=True
    ).select_related('rider', 'team').order_by('rank')[:30]

    youth_results = RaceResult.objects.filter(
        race=race, result_type='youth', stage__isnull=True
    ).select_related('rider', 'team').order_by('rank')[:30]

    stages = Stage.objects.filter(race=race).order_by('number')

    start_list = StartEntry.objects.filter(race=race).select_related(
        'rider', 'team'
    ).order_by('bib_number')[:60]

    editions = Race.objects.filter(slug=slug).exclude(year=year).order_by('-year')[:10]

    winners_history = Race.objects.filter(slug=slug, winner__isnull=False).order_by(
        '-year'
    ).values('year', 'winner', 'winner_team')[:10]

    if request.headers.get('HX-Request'):
        fragment = request.GET.get('fragment')
        if fragment == 'gc':
            return render(request, 'cycling/partials/_gc_table.html', {
                'gc_results': gc_results,
                'race': race,
                'is_live': is_live,
            })

    return render(request, 'cycling/race_detail.html', {
        'race': race,
        'is_live': is_live,
        'gc_results': gc_results,
        'points_results': points_results,
        'kom_results': kom_results,
        'youth_results': youth_results,
        'stages': stages,
        'start_list': start_list,
        'editions': editions,
        'winners_history': winners_history,
    })


def gc_fragment(request, slug, year):
    race = get_object_or_404(Race, slug=slug, year=year)

    if race.is_live:
        try:
            sync_race(slug, year, live=True)
        except Exception:
            logger.exception('Live sync failed for gc_fragment %s %s', slug, year)

    gc_results = RaceResult.objects.filter(
        race=race, result_type='gc', stage__isnull=True
    ).select_related('rider', 'team').order_by('rank')[:50]

    return render(request, 'cycling/partials/_gc_table.html', {
        'race': race,
        'gc_results': gc_results,
        'is_live': race.is_live,
    })


def stage_results_fragment(request, slug, year, stage_num):
    race = get_object_or_404(Race, slug=slug, year=year)
    stage = get_object_or_404(Stage, race=race, number=stage_num)

    if race.is_live:
        try:
            sync_stage_results(race, stage, live=True)
        except Exception:
            logger.exception(
                'Live sync failed for stage_results_fragment %s %s stage %s',
                slug, year, stage_num,
            )

    results = RaceResult.objects.filter(
        race=race, stage=stage, result_type='stage'
    ).select_related('rider', 'team').order_by('rank')

    return render(request, 'cycling/partials/_stage_results.html', {
        'race': race,
        'stage': stage,
        'results': results,
        'is_live': race.is_live,
    })


def live_bar_fragment(request, slug, year):
    race = get_object_or_404(Race, slug=slug, year=year)
    today = date.today()

    current_stage = (
        Stage.objects.filter(race=race, date=today).first()
        or Stage.objects.filter(race=race).order_by('-number').first()
    )

    return render(request, 'cycling/partials/_live_bar.html', {
        'race': race,
        'current_stage': current_stage,
        'is_live': race.is_live,
    })


def stage_detail(request, slug, year, stage_num):
    race = get_object_or_404(Race, slug=slug, year=year)
    stage = get_object_or_404(Stage, race=race, number=stage_num)

    stage_results = RaceResult.objects.filter(
        race=race, stage=stage, result_type='stage'
    ).select_related('rider', 'team').order_by('rank')[:50]

    gc_after = RaceResult.objects.filter(
        race=race, result_type='gc', stage__isnull=True
    ).select_related('rider', 'team').order_by('rank')[:20]

    prev_stage = Stage.objects.filter(race=race, number=stage_num - 1).first()
    next_stage = Stage.objects.filter(race=race, number=stage_num + 1).first()

    return render(request, 'cycling/stage_detail.html', {
        'race': race,
        'stage': stage,
        'stage_results': stage_results,
        'gc_after': gc_after,
        'prev_stage': prev_stage,
        'next_stage': next_stage,
    })


def rider_list(request):
    nationality = request.GET.get('nationality', '')
    q = request.GET.get('q', '')

    riders = Rider.objects.filter(is_active=True).order_by('pcs_rank', 'name')

    if nationality:
        riders = riders.filter(nationality=nationality)
    if q:
        riders = riders.filter(name__icontains=q)

    nationalities = (
        Rider.objects.filter(is_active=True)
        .values_list('nationality', flat=True)
        .distinct()
        .order_by('nationality')
    )

    paginator = Paginator(riders, 60)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'cycling/rider_list.html', {
        'page_obj': page,
        'nationality': nationality,
        'q': q,
        'nationalities': nationalities,
    })


def rider_detail(request, slug):
    rider = get_object_or_404(Rider, slug=slug)

    recent_results = RaceResult.objects.filter(rider=rider).select_related(
        'race', 'team', 'stage'
    ).order_by('-race__end_date')[:20]

    season_years = (
        RaceResult.objects.filter(rider=rider)
        .values_list('race__year', flat=True)
        .distinct()
        .order_by('-race__year')
    )

    return render(request, 'cycling/rider_detail.html', {
        'rider': rider,
        'recent_results': recent_results,
        'season_years': season_years,
    })


def team_list(request):
    current_year = date.today().year
    year = int(request.GET.get('year', current_year))
    status = request.GET.get('status', '')

    teams = Team.objects.filter(year=year).order_by('name')

    if status:
        teams = teams.filter(status=status)

    return render(request, 'cycling/team_list.html', {
        'teams': teams,
        'year': year,
        'years_available': range(current_year + 1, 2019, -1),
        'status': status,
    })


def team_detail(request, slug, year):
    team = get_object_or_404(Team, slug=slug, year=year)

    riders = Rider.objects.filter(team=team, year=year).order_by('pcs_rank', 'name')

    race_results = RaceResult.objects.filter(
        team=team, result_type='gc', stage__isnull=True
    ).select_related('race', 'rider').order_by('-race__end_date')[:20]

    return render(request, 'cycling/team_detail.html', {
        'team': team,
        'riders': riders,
        'race_results': race_results,
    })


def live_dashboard(request):
    ongoing = find_ongoing_races()

    races_data = []
    for race in ongoing:
        today = date.today()
        current_stage = (
            Stage.objects.filter(race=race, date=today).first()
            or Stage.objects.filter(race=race).order_by('-number').first()
        )

        gc_top10 = RaceResult.objects.filter(
            race=race, result_type='gc', stage__isnull=True
        ).select_related('rider', 'team').order_by('rank')[:10]

        stage_results = []
        if current_stage:
            stage_results = RaceResult.objects.filter(
                race=race, stage=current_stage, result_type='stage'
            ).select_related('rider', 'team').order_by('rank')[:20]

        races_data.append({
            'race': race,
            'current_stage': current_stage,
            'gc_top10': gc_top10,
            'stage_results': stage_results,
        })

    return render(request, 'cycling/live_dashboard.html', {
        'races_data': races_data,
    })


def search(request):
    q = request.GET.get('q', '').strip()

    riders = []
    races = []
    teams = []

    if q:
        riders = Rider.objects.filter(name__icontains=q).order_by('pcs_rank', 'name')[:20]
        races = Race.objects.filter(name__icontains=q).order_by('-year')[:20]
        teams = Team.objects.filter(
            name__icontains=q, year__gte=date.today().year - 1
        ).order_by('-year')[:20]

    return render(request, 'cycling/search.html', {
        'q': q,
        'riders': riders,
        'races': races,
        'teams': teams,
    })


def search_autocomplete(request):
    q = request.GET.get('q', '').strip()
    suggestions = []

    if q:
        for rider in Rider.objects.filter(name__icontains=q).order_by('pcs_rank', 'name')[:5]:
            suggestions.append({
                'type': 'rider',
                'name': rider.name,
                'slug': rider.slug,
                'url': rider.get_absolute_url(),
                'subtitle': rider.nationality,
            })

        for race in Race.objects.filter(name__icontains=q).order_by('-year')[:5]:
            suggestions.append({
                'type': 'race',
                'name': race.name,
                'slug': race.slug,
                'url': race.get_absolute_url(),
                'subtitle': str(race.year),
            })

        for team in Team.objects.filter(
            name__icontains=q, year__gte=date.today().year - 1
        ).order_by('-year')[:5]:
            suggestions.append({
                'type': 'team',
                'name': team.name,
                'slug': team.slug,
                'url': team.get_absolute_url(),
                'subtitle': f'{team.year} · {team.status}',
            })

    return JsonResponse({'suggestions': suggestions})


def about(request):
    return render(request, 'cycling/about.html')


def _run_sync(job_id, sync_type, years):
    cache_key_log = f'sync:{job_id}:log'
    cache_key_done = f'sync:{job_id}:done'
    log_lines = []

    def log(msg):
        log_lines.append(msg)
        cache.set(cache_key_log, log_lines, timeout=3600)

    try:
        log(f'Starting sync: {sync_type} for years {list(years)}')

        for year in years:
            if sync_type in ('races', 'all'):
                log(f'Syncing races {year}...')
                count = sync_races_year(year)
                log(f'  → {count} races saved')

            if sync_type in ('teams', 'all'):
                log(f'Syncing teams {year}...')
                for team in Team.objects.filter(year=year):
                    try:
                        sync_team(team.slug, year)
                    except Exception as exc:
                        log(f'  [ERROR] team {team.slug}: {exc}')
                log(f'  → teams done')

            if sync_type in ('results', 'all'):
                log(f'Syncing race results {year}...')
                for race in Race.objects.filter(year=year):
                    try:
                        sync_race(race.slug, year)
                        stages = sync_stages(race)
                        for stage in stages:
                            sync_stage_results(race, stage)
                    except Exception as exc:
                        log(f'  [ERROR] race {race.slug}: {exc}')
                log(f'  → results done')

            if sync_type in ('riders', 'all'):
                log(f'Syncing rankings {year}...')
                try:
                    count = sync_rankings(year)
                    log(f'  → {count} riders updated')
                except Exception as exc:
                    log(f'  [ERROR] rankings: {exc}')

            if sync_type in ('rosters', 'all'):
                log(f'Syncing rosters {year}...')
                for team in Team.objects.filter(year=year):
                    try:
                        sync_team(team.slug, year)
                    except Exception as exc:
                        log(f'  [ERROR] roster {team.slug}: {exc}')
                log(f'  → rosters done')

        log('Sync complete.')
    except Exception as exc:
        log(f'[FATAL] {exc}')
    finally:
        cache.set(cache_key_done, True, timeout=3600)


@staff_member_required
def sync_page(request):
    if request.method == 'POST':
        sync_type = request.POST.get('sync_type', 'races')
        years_raw = request.POST.getlist('years')
        years = [int(y) for y in years_raw if y.isdigit()]
        if not years:
            years = [date.today().year]

        job_id = str(uuid.uuid4())
        thread = threading.Thread(
            target=_run_sync,
            args=(job_id, sync_type, years),
            daemon=True,
        )
        thread.start()
        return JsonResponse({'job_id': job_id})

    current_year = date.today().year
    return render(request, 'cycling/sync.html', {
        'sync_types': SYNC_TYPES,
        'years_available': range(current_year + 1, 2019, -1),
        'current_year': current_year,
    })


@staff_member_required
def sync_status_api(request, job_id):
    offset = int(request.GET.get('offset', 0))
    log_lines = cache.get(f'sync:{job_id}:log', [])
    done = cache.get(f'sync:{job_id}:done', False)

    return JsonResponse({
        'lines': log_lines[offset:],
        'total': len(log_lines),
        'done': done,
    })
