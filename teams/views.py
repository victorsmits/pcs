import logging
from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.contrib import messages

from teams.models import Team, TeamRoster
from teams.services import fetch_teams_by_year, fetch_team_detail

logger = logging.getLogger(__name__)

CURRENT_YEAR = date.today().year


def team_list(request):
    year = request.GET.get('year', CURRENT_YEAR)
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = CURRENT_YEAR

    status = request.GET.get('status', '').strip()
    nationality = request.GET.get('nationality', '').strip()
    search_q = request.GET.get('q', '').strip()

    qs = Team.objects.filter(year=year)

    if status:
        qs = qs.filter(status=status)
    if nationality:
        qs = qs.filter(nationality=nationality)
    if search_q:
        qs = qs.filter(Q(name__icontains=search_q))

    qs = qs.order_by('status', 'name').annotate(rider_count=Count('roster'))

    years_available = list(range(CURRENT_YEAR, 2000, -1))
    status_choices = Team._meta.get_field('status').choices

    paginator = Paginator(qs, 40)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'teams': page_obj.object_list,
        'year': year,
        'years_available': years_available,
        'status': status,
        'nationality': nationality,
        'search_q': search_q,
        'status_choices': status_choices,
        'total_count': qs.count(),
        'page_title': f'Équipes {year}',
    }
    return render(request, 'teams/team_list.html', context)


def team_detail(request, slug, year):
    team = get_object_or_404(Team, slug=slug, year=year)

    refresh = request.GET.get('refresh', False)
    if refresh:
        try:
            team = fetch_team_detail(slug, year) or team
            messages.success(request, f"Données de {team.name} mises à jour.")
        except Exception as exc:
            logger.warning("Failed to refresh team %s %s: %s", slug, year, exc)
            messages.warning(request, "Impossible de récupérer les données.")

    roster = (
        TeamRoster.objects.filter(team=team)
        .select_related('rider')
        .order_by('rider__name')
    )

    from riders.models import RaceResult
    team_results = (
        RaceResult.objects.filter(team=team, year=year, result_type='gc', rank__isnull=False)
        .select_related('rider', 'race')
        .order_by('rank')[:30]
    )

    wins = RaceResult.objects.filter(team=team, year=year, rank=1).count()

    editions = Team.objects.filter(slug=slug).exclude(year=year).order_by('-year')[:10]

    context = {
        'team': team,
        'roster': roster,
        'team_results': team_results,
        'wins': wins,
        'editions': editions,
        'year': year,
        'page_title': f"{team.name} {year}",
    }
    return render(request, 'teams/team_detail.html', context)


def team_fetch(request, slug, year):
    """Trigger a live fetch of team data from PCS."""
    try:
        team = fetch_team_detail(slug, year)
        if team:
            messages.success(request, f"Données de {team.name} {year} récupérées avec succès.")
        else:
            messages.error(request, "Impossible de récupérer les données de l'équipe.")
    except Exception as exc:
        logger.error("Error fetching team %s %s: %s", slug, year, exc)
        messages.error(request, f"Erreur: {exc}")
    return redirect('teams:team_detail', slug=slug, year=year)
