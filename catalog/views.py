"""Vues catalogue. Phase 0 : squelettes rendant des gabarits de base.
Les vues seront enrichies en Phase 1 (fetch à la demande, contenus réels)."""
from datetime import date

from django.shortcuts import render, get_object_or_404

from catalog.models import Race, Stage, Rider, Team, Ranking
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
    stages = race.stages.all().order_by('number')
    return render(request, 'catalog/race_detail.html', {'race': race, 'stages': stages, 'page_title': str(race)})


def stage_detail(request, slug, year, number):
    stage = get_object_or_404(Stage, race__slug=slug, race__year=year, number=number)
    if not stage.detail_synced_at:
        try:
            services.sync_stage_detail(stage)
        except Exception:  # noqa: BLE001
            pass
    profile = build_profile_svg(stage.elevation_points)
    return render(request, 'catalog/stage_detail.html', {
        'stage': stage, 'race': stage.race, 'profile': profile, 'page_title': str(stage),
    })


def rider_detail(request, slug):
    rider = get_object_or_404(Rider, slug=slug)
    return render(request, 'catalog/rider_detail.html', {'rider': rider, 'page_title': rider.name})


def team_detail(request, slug, year):
    team = get_object_or_404(Team, slug=slug, year=year)
    return render(request, 'catalog/team_detail.html', {'team': team, 'page_title': str(team)})
