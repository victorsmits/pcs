"""Vues catalogue. Phase 0 : squelettes rendant des gabarits de base.
Les vues seront enrichies en Phase 1 (fetch à la demande, contenus réels)."""
from datetime import date

from django.core.paginator import Paginator
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect

from catalog.models import Race, Stage, Rider, Team, Ranking, Result, ClassificationType
from catalog import services
from catalog.profile_svg import build_profile_svg


def home(request):
    today = date.today()
    ongoing = Race.objects.filter(start_date__lte=today, end_date__gte=today).order_by('start_date')
    upcoming = Race.objects.filter(start_date__gt=today).order_by('start_date')[:10]
    recent = Race.objects.filter(end_date__lt=today).order_by('-end_date')[:10]
    return render(request, 'catalog/home.html', {
        'ongoing': ongoing,
        'upcoming': upcoming,
        'recent': recent,
        'page_title': 'Accueil',
    })


_MONTHS_FR = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
              'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
_WEEKDAYS_FR = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']


def _race_color(race):
    c = race.classification or ''
    if 'UWT' in c:
        return 'uwt'
    if 'WWT' in c:
        return 'wwt'
    if 'Pro' in c:
        return 'pro'
    if c.startswith(('1.1', '2.1')):
        return 'cont'
    return 'other'


def race_go_live(request, slug, year):
    """Redirige vers la page live de l'étape du jour (ou la course si pas d'étape)."""
    race = get_object_or_404(Race, slug=slug, year=year)
    if race.is_stage_race:
        if not race.stages.exists():
            try:
                services.sync_race_detail(race)
            except Exception:  # noqa: BLE001
                pass
        today = date.today()
        stage = (race.stages.filter(date=today).first()
                 or race.stages.filter(date__lte=today).order_by('-date').first()
                 or race.stages.order_by('number').first())
        if stage:
            return redirect('live:stage_live', slug=slug, year=year, number=stage.number)
    return redirect('catalog:race_detail', slug=slug, year=year)


def calendar(request):
    import calendar as pycal
    from datetime import timedelta
    today = date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        year, month = today.year, today.month
    month = min(max(month, 1), 12)

    first = date(year, month, 1)
    last = date(year, month, pycal.monthrange(year, month)[1])

    races = Race.objects.filter(start_date__lte=last, end_date__gte=first).order_by('start_date')

    # Bucket des courses par jour
    by_day = {}
    for r in races:
        start = max(r.start_date, first)
        end = min(r.end_date or r.start_date, last)
        d = start
        while d <= end:
            by_day.setdefault(d, []).append({
                'race': r, 'color': _race_color(r),
                'is_start': d == r.start_date,
            })
            d += timedelta(days=1)

    weeks = []
    for week in pycal.Calendar(firstweekday=0).monthdatescalendar(year, month):
        weeks.append([{
            'date': d, 'day': d.day, 'in_month': d.month == month,
            'is_today': d == today, 'races': by_day.get(d, []),
        } for d in week])

    prev_m = (first - timedelta(days=1))
    next_m = (last + timedelta(days=1))

    return render(request, 'catalog/calendar.html', {
        'weeks': weeks, 'year': year, 'month': month,
        'month_name': _MONTHS_FR[month], 'weekdays': _WEEKDAYS_FR,
        'prev': {'year': prev_m.year, 'month': prev_m.month},
        'next': {'year': next_m.year, 'month': next_m.month},
        'page_title': f'Calendrier {_MONTHS_FR[month]} {year}',
    })


def _paginate(request, qs):
    from django.conf import settings
    paginator = Paginator(qs, settings.ITEMS_PER_PAGE)
    return paginator.get_page(request.GET.get('page'))


def race_list(request):
    page = _paginate(request, Race.objects.all().order_by('-start_date', 'name'))
    return render(request, 'catalog/race_list.html', {'races': page, 'page_obj': page, 'page_title': 'Courses'})


def rider_list(request):
    page = _paginate(request, Rider.objects.all().order_by('name'))
    return render(request, 'catalog/rider_list.html', {'riders': page, 'page_obj': page, 'page_title': 'Coureurs'})


def team_list(request):
    page = _paginate(request, Team.objects.filter(year=date.today().year).order_by('name'))
    return render(request, 'catalog/team_list.html', {'teams': page, 'page_obj': page, 'page_title': 'Équipes'})


def rankings(request):
    gender = request.GET.get('g', 'me')
    if gender not in ('me', 'we'):
        gender = 'me'
    year = date.today().year
    if not Ranking.objects.filter(kind=Ranking.Kind.PCS, year=year, gender=gender).exists():
        try:
            services.sync_pcs_ranking(year, gender)
        except Exception:  # noqa: BLE001
            pass
    ranking = (Ranking.objects.filter(kind=Ranking.Kind.PCS, year=year, gender=gender)
               .select_related('rider', 'rider__current_team').order_by('rank')[:100])
    return render(request, 'catalog/rankings.html', {
        'ranking': ranking, 'gender': gender, 'year': year, 'page_title': 'Classement PCS',
    })


def race_detail(request, slug, year):
    race = Race.objects.filter(slug=slug, year=year).first()
    if not race:
        # Édition absente : on la crée si la course existe pour une autre année
        if Race.objects.filter(slug=slug).exists():
            race = services.ensure_edition(slug, year)
        else:
            from django.http import Http404
            raise Http404('Course introuvable')
    if not race.detail_synced_at:
        try:
            services.sync_race_detail(race)
        except Exception:  # noqa: BLE001
            pass
    stages = race.stages.all().order_by('number').select_related('winner')

    today = date.today()
    is_ongoing = bool(race.start_date and race.end_date and race.start_date <= today <= race.end_date)
    gc = []
    oneday = []
    gc_provisional = False
    race_started = bool(race.start_date and race.start_date <= today)
    if race.is_stage_race:
        # Une course non démarrée n'a pas de GC : inutile (et coûteux) de scraper.
        # En course : on rafraîchit le GC provisoire à chaque visite.
        has_gc = Result.objects.filter(race=race, classification=ClassificationType.GC).exists()
        if race_started and (is_ongoing or not has_gc):
            try:
                services.sync_gc(race, force=is_ongoing)
            except Exception:  # noqa: BLE001
                pass
        gc = list(Result.objects.filter(race=race, classification=ClassificationType.GC)
                  .select_related('rider', 'team').order_by(F('rank').asc(nulls_last=True))[:30])
        gc_provisional = is_ongoing and bool(gc) and not any(r.time_gap for r in gc)

    # Porteurs de maillots (depuis la dernière étape disputée)
    jersey_riders = []
    if race.is_stage_race and race_started and (gc or stages):
        try:
            jersey_riders = services.get_jersey_wearers(race)
        except Exception:  # noqa: BLE001
            pass
    else:
        if race_started and not Result.objects.filter(race=race, stage__isnull=True).exists():
            try:
                services.sync_oneday_result(race)
            except Exception:  # noqa: BLE001
                pass
        oneday = (Result.objects.filter(race=race, stage__isnull=True)
                  .select_related('rider', 'team').order_by(F('rank').asc(nulls_last=True))[:30])

    try:
        years = services.get_race_years(race)
    except Exception:  # noqa: BLE001
        years = [race.year]

    return render(request, 'catalog/race_detail.html', {
        'race': race, 'stages': stages, 'gc': gc, 'oneday': oneday,
        'gc_provisional': gc_provisional, 'ongoing_today': is_ongoing,
        'jersey_riders': jersey_riders, 'years': years, 'page_title': str(race),
    })


def search_api(request):
    """Autocomplete : recherche locale instantanée (JSON groupé)."""
    from catalog.search import search_local
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'riders': [], 'teams': [], 'races': [], 'q': q})
    data = search_local(q, limit=5)
    data['q'] = q
    return JsonResponse(data)


def search(request):
    """Page de résultats complète (locale + PCS = globale)."""
    from catalog.search import search_all
    q = request.GET.get('q', '').strip()
    results = search_all(q, limit=12, include_pcs=True) if len(q) >= 2 else {'riders': [], 'teams': [], 'races': []}
    total = sum(len(results[k]) for k in results)
    groups = [
        ('Coureurs', results['riders'], 'rider'),
        ('Équipes', results['teams'], 'team'),
        ('Courses', results['races'], 'race'),
    ]
    return render(request, 'catalog/search.html', {
        'q': q, 'groups': groups, 'total': total,
        'page_title': f'Recherche : {q}' if q else 'Recherche',
    })


def startlist(request, slug, year):
    """Liste des engagés, groupable (équipe / nationalité / alphabétique)."""
    import json
    race = get_object_or_404(Race, slug=slug, year=year)
    from catalog.models import StartListEntry
    if not StartListEntry.objects.filter(race=race).exists():
        try:
            services.sync_startlist(race)
        except Exception:  # noqa: BLE001
            pass
    entries = (StartListEntry.objects.filter(race=race)
               .select_related('rider', 'team').order_by('bib'))
    data = [{
        'bib': e.bib,
        'name': e.rider.name,
        'rider_url': e.rider.get_absolute_url(),
        'nat': (e.rider.nationality or '').upper(),
        'team': e.team.name if e.team else '—',
        'team_url': e.team.get_absolute_url() if e.team else '',
    } for e in entries]
    return render(request, 'catalog/startlist.html', {
        'race': race, 'entries_json': json.dumps(data), 'count': len(data),
        'page_title': f'Engagés — {race.name} {race.year}',
    })


def race_history(request, slug, year):
    """Endpoint JSON : éditions précédentes + vainqueurs (backfill paresseux, caché)."""
    race = get_object_or_404(Race, slug=slug, year=year)
    editions = services.get_past_editions(race, n=6)
    return JsonResponse({'editions': [
        {
            'year': e['year'],
            'url': e['race'].get_absolute_url(),
            'winner': e['winner'].name,
            'winner_url': e['winner'].get_absolute_url(),
        } for e in editions
    ]})


def stage_detail(request, slug, year, number):
    stage = get_object_or_404(Stage, race__slug=slug, race__year=year, number=number)
    if not stage.detail_synced_at:
        try:
            services.sync_stage_detail(stage)
        except Exception:  # noqa: BLE001
            pass
    # Étape déjà synchronisée mais sans profil vectoriel → on reconstruit depuis l'image
    elif not stage.elevation_points and stage.profile_image_url:
        try:
            services.backfill_profile_from_image(stage)
        except Exception:  # noqa: BLE001
            pass
    climbs = [{'km': c.km, 'name': c.name, 'category': c.category} for c in stage.climbs.all()]
    profile = build_profile_svg(stage.elevation_points, stage.min_elevation,
                                stage.max_elevation, stage.distance, climbs=climbs)

    if not Result.objects.filter(stage=stage, classification=ClassificationType.STAGE).exists():
        try:
            services.sync_stage_results(stage)
        except Exception:  # noqa: BLE001
            pass
    results = (Result.objects.filter(stage=stage, classification=ClassificationType.STAGE)
               .select_related('rider', 'team').order_by(F('rank').asc(nulls_last=True))[:30])

    return render(request, 'catalog/stage_detail.html', {
        'stage': stage, 'race': stage.race, 'profile': profile,
        'climbs': stage.climbs.all(), 'results': results, 'page_title': str(stage),
    })


def rider_detail(request, slug):
    rider = get_object_or_404(Rider, slug=slug)
    data = None
    try:
        data = services.sync_rider(rider, force=not rider.detail_synced_at)
        rider.refresh_from_db()
    except Exception:  # noqa: BLE001
        pass
    return render(request, 'catalog/rider_detail.html', {
        'rider': rider, 'top_results': (data or {}).get('top_results', []),
        'page_title': rider.name,
    })


def team_detail(request, slug, year):
    team = get_object_or_404(Team, slug=slug, year=year)
    if not team.detail_synced_at:
        try:
            services.sync_team(team)
            team.refresh_from_db()
        except Exception:  # noqa: BLE001
            pass
    roster = (Rider.objects.filter(memberships__team=team, memberships__year=year)
              .order_by('name').distinct())
    return render(request, 'catalog/team_detail.html', {
        'team': team, 'roster': roster, 'page_title': str(team),
    })
