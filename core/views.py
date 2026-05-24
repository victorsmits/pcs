import logging
import threading
import uuid
from datetime import date, timedelta
from django.shortcuts import render, redirect
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def home(request):
    from races.models import Race
    from riders.models import Rider
    from teams.models import Team

    current_year = date.today().year
    recent_races = Race.objects.filter(
        end_date__lte=date.today(), year=current_year
    ).order_by('-end_date').select_related('winner', 'winner_team')[:6]

    upcoming_races = Race.objects.filter(
        start_date__gt=date.today(), year=current_year
    ).order_by('start_date').select_related('winner')[:6]

    from races.services import find_races_today
    ongoing_races = find_races_today()[:3]

    top_riders = Rider.objects.filter(
        pcs_rank__isnull=False, is_active=True
    ).order_by('pcs_rank')[:10]

    top_teams = Team.objects.filter(
        year=current_year, team_rank__isnull=False
    ).order_by('team_rank')[:10]

    stats = {
        'total_riders': Rider.objects.filter(is_active=True).count(),
        'total_races': Race.objects.filter(year=current_year).count(),
        'total_teams': Team.objects.filter(year=current_year).count(),
    }

    context = {
        'recent_races': recent_races,
        'upcoming_races': upcoming_races,
        'ongoing_races': ongoing_races,
        'top_riders': top_riders,
        'top_teams': top_teams,
        'stats': stats,
        'current_year': current_year,
        'page_title': 'Accueil',
    }
    return render(request, 'core/home.html', context)


def search(request):
    query = request.GET.get('q', '').strip()
    results = {'riders': [], 'races': [], 'teams': []}

    if query and len(query) >= 2:
        from riders.models import Rider
        from races.models import Race
        from teams.models import Team

        results['riders'] = Rider.objects.filter(
            Q(name__icontains=query) | Q(slug__icontains=query)
        ).order_by('pcs_rank', 'name')[:20]

        current_year = date.today().year
        results['races'] = Race.objects.filter(
            Q(name__icontains=query) | Q(country_name__icontains=query)
        ).order_by('-year', 'name')[:20]

        results['teams'] = Team.objects.filter(
            Q(name__icontains=query) | Q(country_name__icontains=query),
            year__gte=current_year - 1
        ).order_by('-year', 'name')[:20]

    total = sum(len(v) for v in results.values())

    context = {
        'query': query,
        'results': results,
        'total_results': total,
        'page_title': f'Recherche: {query}' if query else 'Recherche',
    }
    return render(request, 'core/search.html', context)


def search_autocomplete(request):
    query = request.GET.get('q', '').strip()
    suggestions = []

    if query and len(query) >= 2:
        from riders.models import Rider
        from races.models import Race
        from teams.models import Team

        riders = Rider.objects.filter(name__icontains=query).values('name', 'slug', 'nationality')[:5]
        for r in riders:
            suggestions.append({
                'type': 'rider', 'name': r['name'], 'slug': r['slug'],
                'url': f"/riders/{r['slug']}/", 'subtitle': r.get('nationality', '')
            })

        races = Race.objects.filter(name__icontains=query).values('name', 'slug', 'year').order_by('-year')[:5]
        for r in races:
            suggestions.append({
                'type': 'race', 'name': r['name'], 'slug': r['slug'],
                'url': f"/races/{r['slug']}/{r['year']}/", 'subtitle': str(r['year'])
            })

        teams = Team.objects.filter(name__icontains=query).values('name', 'slug', 'year').order_by('-year')[:5]
        for t in teams:
            suggestions.append({
                'type': 'team', 'name': t['name'], 'slug': t['slug'],
                'url': f"/teams/{t['slug']}/{t['year']}/", 'subtitle': str(t['year'])
            })

    return JsonResponse({'suggestions': suggestions})


def about(request):
    return render(request, 'core/about.html', {'page_title': 'À propos'})


# ---------------------------------------------------------------------------
# SYNC VIEWS
# ---------------------------------------------------------------------------

SYNC_TYPES = [
    ('races',         'Courses (liste)'),
    ('teams',         'Équipes'),
    ('results',       'Résultats / Détails courses'),
    ('riders',        'Coureurs + Classements'),
    ('rosters',       'Effectifs équipes'),
    ('nationalities', 'Nationalités + liaisons'),
    ('all',           'Tout synchroniser'),
]


def _run_sync(job_id, sync_type, years):
    """Run sync in background thread, storing progress in cache."""
    log_key  = f'sync:{job_id}:log'
    done_key = f'sync:{job_id}:done'
    err_key  = f'sync:{job_id}:err'

    def log(msg, level='info'):
        lines = cache.get(log_key, [])
        lines.append({'msg': msg, 'level': level})
        cache.set(log_key, lines, timeout=7200)

    try:
        log(f'▶ Démarrage — type={sync_type}  années={years}')

        if sync_type in ('all', 'races'):
            from races.services import fetch_races_by_year
            from races.models import Race
            for year in years:
                log(f'  ↻ Courses {year}...')
                fetch_races_by_year(year)
                n = Race.objects.filter(year=year).count()
                log(f'  ✓ Courses {year} — {n} en base', 'success')

        if sync_type in ('all', 'teams'):
            from teams.services import fetch_teams_by_year
            from teams.models import Team
            for year in years:
                log(f'  ↻ Équipes {year}...')
                fetch_teams_by_year(year)
                n = Team.objects.filter(year=year).count()
                log(f'  ✓ Équipes {year} — {n} en base', 'success')

        if sync_type in ('all', 'riders'):
            from riders.models import Rider
            from rankings.models import RiderRanking
            from core.services import pcs_get
            log('  ↻ Coureurs top-500 + classements...')
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
                        slug=slug, defaults={'name': name, 'nationality': nat, 'pcs_rank': rank}
                    )
                    RiderRanking.objects.update_or_create(
                        rider=rider, year=date.today().year, ranking_type='pcs',
                        defaults={'rank': rank, 'points': pts}
                    )
                    saved += 1
            log(f'  ✓ Coureurs — {saved} traités', 'success')

        if sync_type in ('all', 'results'):
            from races.services import fetch_race_detail
            from races.models import Race
            from riders.models import RaceResult
            today = date.today()
            qs = list(Race.objects.filter(year__in=years, end_date__lte=today).order_by('year', 'end_date'))
            log(f'  ↻ Résultats — {len(qs)} courses terminées...')
            ok = err = 0
            for race in qs:
                try:
                    fetch_race_detail(race.slug, race.year)
                    ok += 1
                    if ok % 10 == 0:
                        log(f'    {ok}/{len(qs)} courses traitées')
                except Exception as exc:
                    err += 1
                    logger.debug('sync results ERR %s %d: %s', race.slug, race.year, exc)
            log(f'  ✓ Résultats — {ok} OK / {err} erreurs', 'success')

        if sync_type in ('all', 'rosters'):
            from teams.services import fetch_team_detail
            from teams.models import Team
            qs = list(Team.objects.filter(year__in=years))
            log(f'  ↻ Effectifs — {len(qs)} équipes...')
            ok = err = 0
            for team in qs:
                try:
                    fetch_team_detail(team.slug, team.year)
                    ok += 1
                except Exception as exc:
                    err += 1
                    logger.debug('sync roster ERR %s %d: %s', team.slug, team.year, exc)
            log(f'  ✓ Effectifs — {ok} OK / {err} erreurs', 'success')

        if sync_type in ('all', 'nationalities'):
            from riders.models import Rider
            from core.services import pcs_get
            log('  ↻ Nationalités...')
            updated = 0
            for offset in range(0, 600, 100):
                url = f'https://www.procyclingstats.com/rankings.php?s=season-individual&offset={offset}'
                soup = pcs_get(url)
                if not soup:
                    break
                table = soup.find('table', class_='basic')
                if not table:
                    break
                for row in table.select('tbody tr'):
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
            empty = Rider.objects.filter(nationality='').count()
            log(f'  ✓ Nationalités — {updated} mis à jour / {empty} encore vides', 'success')

        from races.models import Race as _Race
        from teams.models import Team as _Team
        from riders.models import Rider as _Rider, RaceResult as _RR
        log(f'✔ Terminé — {_Race.objects.count()} courses · {_Team.objects.count()} équipes · {_Rider.objects.count()} coureurs · {_RR.objects.count()} résultats', 'success')
    except Exception as exc:
        logger.error('sync job %s crashed: %s', job_id, exc)
        log(f'✗ Erreur fatale: {exc}', 'error')
        cache.set(err_key, str(exc), timeout=7200)
    finally:
        cache.set(done_key, True, timeout=7200)


@staff_member_required
def sync_page(request):
    years_available = list(range(date.today().year + 1, 2019, -1))
    qyear = request.GET.get('year', '')
    default_years = [qyear] if qyear.isdigit() else [str(date.today().year)]

    if request.method == 'POST':
        sync_type = request.POST.get('sync_type', 'races')
        years_raw = request.POST.getlist('years')
        years = [int(y) for y in years_raw if y.isdigit()]
        if not years:
            years = [date.today().year]
        job_id = uuid.uuid4().hex
        cache.set(f'sync:{job_id}:log',  [], timeout=7200)
        cache.set(f'sync:{job_id}:done', False, timeout=7200)
        threading.Thread(
            target=_run_sync, args=(job_id, sync_type, years), daemon=True
        ).start()
        return JsonResponse({'job_id': job_id})

    context = {
        'years_available': years_available,
        'default_years': default_years,
        'sync_types': SYNC_TYPES,
        'page_title': 'Synchronisation PCS',
    }
    return render(request, 'core/sync.html', context)


@staff_member_required
def sync_status_api(request, job_id):
    log_key  = f'sync:{job_id}:log'
    done_key = f'sync:{job_id}:done'
    offset = int(request.GET.get('offset', 0))
    lines = cache.get(log_key, [])
    done  = cache.get(done_key, False)
    return JsonResponse({'lines': lines[offset:], 'total': len(lines), 'done': done})


def stats_overview(request):
    from riders.models import Rider, RaceResult
    from races.models import Race
    from teams.models import Team

    current_year = date.today().year

    rider_nationalities = Rider.objects.filter(
        is_active=True, nationality__gt=''
    ).values('nationality').annotate(count=Count('id')).order_by('-count')[:15]

    race_classifications = Race.objects.filter(
        year=current_year, classification__gt=''
    ).values('classification').annotate(count=Count('id')).order_by('-count')[:10]

    context = {
        'rider_nationalities': list(rider_nationalities),
        'race_classifications': list(race_classifications),
        'current_year': current_year,
        'page_title': 'Statistiques globales',
    }
    return render(request, 'core/stats.html', context)
