import logging
from datetime import date
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q

from rankings.models import RiderRanking, TeamRanking

logger = logging.getLogger(__name__)

CURRENT_YEAR = date.today().year


def individual_rankings(request):
    year = request.GET.get('year', CURRENT_YEAR)
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = CURRENT_YEAR

    ranking_type = request.GET.get('type', 'pcs')
    nationality = request.GET.get('nationality', '').strip()
    search_q = request.GET.get('q', '').strip()

    qs = RiderRanking.objects.filter(
        ranking_type=ranking_type, year=year
    ).select_related('rider', 'team').order_by('rank')

    if nationality:
        qs = qs.filter(nationality=nationality)
    if search_q:
        qs = qs.filter(Q(rider__name__icontains=search_q))

    years_available = list(range(CURRENT_YEAR, 2000, -1))

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'rankings': page_obj.object_list,
        'year': year,
        'ranking_type': ranking_type,
        'nationality': nationality,
        'search_q': search_q,
        'years_available': years_available,
        'ranking_types': [('pcs', 'PCS Points'), ('uci', 'UCI Points'), ('wins', 'Victoires')],
        'total_count': qs.count(),
        'page_title': f'Classement individuel {year}',
    }
    return render(request, 'rankings/individual_rankings.html', context)


def team_rankings(request):
    year = request.GET.get('year', CURRENT_YEAR)
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = CURRENT_YEAR

    ranking_type = request.GET.get('type', 'uci_team')
    search_q = request.GET.get('q', '').strip()

    qs = TeamRanking.objects.filter(
        ranking_type=ranking_type, year=year
    ).select_related('team').order_by('rank')

    if search_q:
        qs = qs.filter(Q(team__name__icontains=search_q))

    years_available = list(range(CURRENT_YEAR, 2000, -1))

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'rankings': page_obj.object_list,
        'year': year,
        'ranking_type': ranking_type,
        'search_q': search_q,
        'years_available': years_available,
        'ranking_types': [('uci_team', 'UCI Équipes'), ('pcs', 'PCS Équipes'), ('wins', 'Victoires')],
        'total_count': qs.count(),
        'page_title': f'Classement équipes {year}',
    }
    return render(request, 'rankings/team_rankings.html', context)
