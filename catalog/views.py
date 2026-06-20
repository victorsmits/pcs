"""Vues catalogue. Phase 0 : squelettes rendant des gabarits de base.
Les vues seront enrichies en Phase 1 (fetch à la demande, contenus réels)."""
from datetime import date

from django.db.models import F
from django.shortcuts import render, get_object_or_404

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


def calendar(request):
    year = int(request.GET.get('year', date.today().year))
    races = Race.objects.filter(year=year).order_by('start_date')
    return render(request, 'catalog/calendar.html', {'races': races, 'year': year, 'page_title': f'Calendrier {year}'})


def race_list(request):
    races = Race.objects.all().order_by('-start_date')[:100]
    return render(request, 'catalog/race_list.html', {'races': races, 'page_title': 'Courses'})


def rider_list(request):
    riders = Rider.objects.all().order_by('name')[:100]
    return render(request, 'catalog/rider_list.html', {'riders': riders, 'page_title': 'Coureurs'})


def team_list(request):
    teams = Team.objects.filter(year=date.today().year).order_by('name')
    return render(request, 'catalog/team_list.html', {'teams': teams, 'page_title': 'Équipes'})


def rankings(request):
    kind = request.GET.get('kind', 'pcs')
    year = int(request.GET.get('year', date.today().year))
    ranking = Ranking.objects.filter(kind=kind, year=year).select_related('rider', 'team').order_by('rank')[:100]
    return render(request, 'catalog/rankings.html', {
        'ranking': ranking, 'kind': kind, 'year': year, 'page_title': 'Classements',
    })


def race_detail(request, slug, year):
    race = get_object_or_404(Race, slug=slug, year=year)
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
    if race.is_stage_race:
        # En course : on rafraîchit le GC provisoire à chaque visite
        if is_ongoing or not Result.objects.filter(race=race, classification=ClassificationType.GC).exists():
            try:
                services.sync_gc(race, force=is_ongoing)
            except Exception:  # noqa: BLE001
                pass
        gc = list(Result.objects.filter(race=race, classification=ClassificationType.GC)
                  .select_related('rider', 'team').order_by(F('rank').asc(nulls_last=True))[:30])
        gc_provisional = is_ongoing and bool(gc) and not any(r.time_gap for r in gc)
    else:
        if not Result.objects.filter(race=race, stage__isnull=True).exists():
            try:
                services.sync_oneday_result(race)
            except Exception:  # noqa: BLE001
                pass
        oneday = (Result.objects.filter(race=race, stage__isnull=True)
                  .select_related('rider', 'team').order_by(F('rank').asc(nulls_last=True))[:30])

    return render(request, 'catalog/race_detail.html', {
        'race': race, 'stages': stages, 'gc': gc, 'oneday': oneday,
        'gc_provisional': gc_provisional, 'ongoing_today': is_ongoing, 'page_title': str(race),
    })


def stage_detail(request, slug, year, number):
    stage = get_object_or_404(Stage, race__slug=slug, race__year=year, number=number)
    if not stage.detail_synced_at:
        try:
            services.sync_stage_detail(stage)
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
    return render(request, 'catalog/rider_detail.html', {'rider': rider, 'page_title': rider.name})


def team_detail(request, slug, year):
    team = get_object_or_404(Team, slug=slug, year=year)
    return render(request, 'catalog/team_detail.html', {'team': team, 'page_title': str(team)})
