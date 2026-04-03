import logging
from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.contrib import messages

from races.models import Race, Stage, StartList
from races.services import fetch_races_by_year, fetch_race_detail, fetch_stages_for_race
from riders.models import RaceResult

logger = logging.getLogger(__name__)

CURRENT_YEAR = date.today().year


def race_list(request):
    year = request.GET.get('year', CURRENT_YEAR)
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = CURRENT_YEAR

    classification = request.GET.get('classification', '').strip()
    circuit = request.GET.get('circuit', '').strip()
    search_q = request.GET.get('q', '').strip()
    show_type = request.GET.get('type', 'all')

    qs = Race.objects.filter(year=year).order_by('start_date', 'name')

    if classification:
        qs = qs.filter(classification=classification)
    if circuit:
        qs = qs.filter(circuit__icontains=circuit)
    if search_q:
        qs = qs.filter(name__icontains=search_q)
    if show_type == 'stage':
        qs = qs.filter(is_stage_race=True)
    elif show_type == 'oneday':
        qs = qs.filter(is_stage_race=False)
    elif show_type == 'grand_tour':
        qs = qs.filter(is_grand_tour=True)
    elif show_type == 'monument':
        qs = qs.filter(is_monument=True)

    qs = qs.select_related('winner', 'winner_team')

    years_available = list(range(CURRENT_YEAR, 2000, -1))
    classifications = Race.objects.values_list('classification', flat=True).distinct().order_by('classification')

    paginator = Paginator(qs, 40)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'races': page_obj.object_list,
        'year': year,
        'years_available': years_available,
        'classification': classification,
        'circuit': circuit,
        'search_q': search_q,
        'show_type': show_type,
        'classifications': list(classifications),
        'total_count': qs.count(),
        'page_title': f'Courses {year}',
    }
    return render(request, 'races/race_list.html', context)


def race_detail(request, slug, year):
    race = get_object_or_404(Race, slug=slug, year=year)

    refresh = request.GET.get('refresh', False)
    if refresh:
        try:
            race = fetch_race_detail(slug, year) or race
            messages.success(request, f"Données de {race.name} mises à jour.")
        except Exception as exc:
            logger.warning("Failed to refresh race %s %s: %s", slug, year, exc)
            messages.warning(request, "Impossible de récupérer les données en temps réel.")

    gc_results = (
        RaceResult.objects.filter(race=race, result_type='gc', stage__isnull=True)
        .select_related('rider', 'team')
        .order_by('rank')[:50]
    )

    stages = Stage.objects.filter(race=race).order_by('number')

    start_list = StartList.objects.filter(race=race).select_related('rider', 'team').order_by('bib_number')

    editions = Race.objects.filter(slug=slug).exclude(year=year).order_by('-year')[:10]

    winners_history = (
        Race.objects.filter(slug=slug, winner__isnull=False)
        .select_related('winner', 'winner_team')
        .order_by('-year')[:10]
    )

    context = {
        'race': race,
        'gc_results': gc_results,
        'stages': stages,
        'start_list': start_list[:30],
        'editions': editions,
        'winners_history': winners_history,
        'year': year,
        'page_title': f"{race.name} {year}",
    }
    return render(request, 'races/race_detail.html', context)


def stage_list(request, slug, year):
    race = get_object_or_404(Race, slug=slug, year=year)
    stages = Stage.objects.filter(race=race).order_by('number').select_related('winner', 'winner_team', 'leader_after')

    if not stages.exists():
        refresh = request.GET.get('refresh', False)
        if refresh:
            try:
                fetched = fetch_stages_for_race(race)
                stages = Stage.objects.filter(race=race).order_by('number')
                messages.success(request, f"{len(fetched)} étapes récupérées.")
            except Exception as exc:
                logger.warning("Failed to fetch stages: %s", exc)

    context = {
        'race': race,
        'stages': stages,
        'year': year,
        'page_title': f"{race.name} {year} - Étapes",
    }
    return render(request, 'races/stage_list.html', context)


def stage_detail(request, slug, year, stage_num):
    race = get_object_or_404(Race, slug=slug, year=year)
    stage = get_object_or_404(Stage, race=race, number=stage_num)

    stage_results = (
        RaceResult.objects.filter(race=race, stage=stage, result_type='stage')
        .select_related('rider', 'team')
        .order_by('rank')[:50]
    )

    gc_after_stage = (
        RaceResult.objects.filter(race=race, stage=stage, result_type='gc')
        .select_related('rider', 'team')
        .order_by('rank')[:20]
    )

    prev_stage = Stage.objects.filter(race=race, number=stage_num - 1).first()
    next_stage = Stage.objects.filter(race=race, number=stage_num + 1).first()

    context = {
        'race': race,
        'stage': stage,
        'stage_results': stage_results,
        'gc_after_stage': gc_after_stage,
        'prev_stage': prev_stage,
        'next_stage': next_stage,
        'year': year,
        'page_title': f"{race.name} {year} - Étape {stage_num}",
    }
    return render(request, 'races/stage_detail.html', context)


def race_fetch(request, slug, year):
    """Trigger a live fetch of race data from PCS."""
    try:
        race = fetch_race_detail(slug, year)
        if race:
            messages.success(request, f"Données de {race.name} {year} récupérées avec succès.")
        else:
            messages.error(request, "Impossible de récupérer les données de la course.")
    except Exception as exc:
        logger.error("Error fetching race %s %s: %s", slug, year, exc)
        messages.error(request, f"Erreur: {exc}")
    return redirect('races:race_detail', slug=slug, year=year)


def race_calendar(request):
    year = request.GET.get('year', CURRENT_YEAR)
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = CURRENT_YEAR

    races = Race.objects.filter(year=year, start_date__isnull=False).order_by('start_date')
    years_available = list(range(CURRENT_YEAR, 2000, -1))

    import json
    calendar_events = []
    for race in races:
        calendar_events.append({
            'title': race.name,
            'start': race.start_date.isoformat() if race.start_date else None,
            'end': race.end_date.isoformat() if race.end_date else None,
            'url': race.get_absolute_url(),
            'color': _get_race_color(race),
        })

    context = {
        'races': races,
        'year': year,
        'years_available': years_available,
        'calendar_events_json': json.dumps(calendar_events),
        'page_title': f'Calendrier {year}',
    }
    return render(request, 'races/race_calendar.html', context)


def _get_race_color(race):
    if race.is_grand_tour:
        return '#e74c3c'
    if race.is_monument:
        return '#f39c12'
    if race.classification in ('1.UWT', '2.UWT'):
        return '#3498db'
    if race.classification in ('1.Pro', '2.Pro'):
        return '#2ecc71'
    return '#95a5a6'
