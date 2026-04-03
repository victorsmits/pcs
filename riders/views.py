import logging
from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg, Min
from django.http import JsonResponse, Http404
from django.contrib import messages

from riders.models import Rider, RaceResult, RiderSeasonStats
from riders.services import fetch_rider_from_pcs, get_rider_career_stats

logger = logging.getLogger(__name__)

NATIONALITY_NAMES = {
    'FRA': 'France', 'BEL': 'Belgique', 'ITA': 'Italie', 'ESP': 'Espagne',
    'GBR': 'Grande-Bretagne', 'DEU': 'Allemagne', 'NLD': 'Pays-Bas', 'SVN': 'Slovénie',
    'COL': 'Colombie', 'AUS': 'Australie', 'DNK': 'Danemark', 'NOR': 'Norvège',
    'SWE': 'Suède', 'CHE': 'Suisse', 'USA': 'États-Unis', 'POL': 'Pologne',
    'PRT': 'Portugal', 'KAZ': 'Kazakhstan', 'RUS': 'Russie', 'UKR': 'Ukraine',
    'NZL': 'Nouvelle-Zélande', 'RWA': 'Rwanda', 'ERI': 'Érythrée', 'RSA': 'Afrique du Sud',
    'ARG': 'Argentine', 'COL': 'Colombie', 'AUT': 'Autriche', 'CZE': 'Rép. Tchèque',
    'SVK': 'Slovaquie', 'LTU': 'Lituanie', 'LAT': 'Lettonie', 'EST': 'Estonie',
}


def rider_list(request):
    qs = Rider.objects.select_related('current_team').all()

    search_q = request.GET.get('q', '').strip()
    nationality = request.GET.get('nationality', '').strip()
    specialty = request.GET.get('specialty', '').strip()
    team_id = request.GET.get('team', '').strip()
    sort = request.GET.get('sort', 'rank')

    if search_q:
        qs = qs.filter(Q(name__icontains=search_q))
    if nationality:
        qs = qs.filter(nationality=nationality)
    if specialty:
        qs = qs.filter(specialty=specialty)
    if team_id:
        qs = qs.filter(current_team_id=team_id)

    sort_options = {
        'rank': 'pcs_rank', '-rank': '-pcs_rank',
        'name': 'name', '-name': '-name',
        'wins': '-one_day_wins', 'points': '-pcs_points',
    }
    qs = qs.order_by(sort_options.get(sort, 'pcs_rank'), 'pcs_rank', 'name')

    nationalities = (
        Rider.objects.filter(nationality__gt='', is_active=True)
        .values('nationality')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )
    nat_list = [
        {'code': n['nationality'], 'name': NATIONALITY_NAMES.get(n['nationality'], n['nationality']), 'count': n['count']}
        for n in nationalities
    ]

    paginator = Paginator(qs, 50)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        'page_obj': page_obj,
        'riders': page_obj.object_list,
        'search_q': search_q,
        'nationality': nationality,
        'specialty': specialty,
        'sort': sort,
        'nationalities': nat_list,
        'specialty_choices': Rider._meta.get_field('specialty').choices,
        'total_count': qs.count(),
        'page_title': 'Coureurs',
    }
    return render(request, 'riders/rider_list.html', context)


def rider_detail(request, slug):
    rider = get_object_or_404(Rider, slug=slug)

    refresh = request.GET.get('refresh', False)
    if refresh or not rider.name:
        try:
            rider = fetch_rider_from_pcs(slug) or rider
            messages.success(request, f"Données de {rider.name} mises à jour.")
        except Exception as exc:
            logger.warning("Failed to refresh rider %s: %s", slug, exc)
            messages.warning(request, "Impossible de récupérer les données en temps réel.")

    race_results = (
        RaceResult.objects.filter(rider=rider, result_type='gc')
        .select_related('race', 'team')
        .order_by('-year', '-race__start_date')
    )

    years = race_results.values_list('year', flat=True).distinct().order_by('-year')

    selected_year = request.GET.get('year', '')
    if selected_year:
        try:
            race_results = race_results.filter(year=int(selected_year))
        except ValueError:
            pass

    wins = race_results.filter(rank=1).count()
    podiums = race_results.filter(rank__lte=3).count()
    top10 = race_results.filter(rank__lte=10).count()
    total_results = race_results.count()

    season_stats = RiderSeasonStats.objects.filter(rider=rider).order_by('-year')

    wins_by_year = (
        RaceResult.objects.filter(rider=rider, rank=1)
        .values('year')
        .annotate(count=Count('id'))
        .order_by('year')
    )

    team_history = rider.team_history.select_related('team').order_by('-team__year')

    paginator = Paginator(race_results, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'rider': rider,
        'page_obj': page_obj,
        'results': page_obj.object_list,
        'years': list(years),
        'selected_year': selected_year,
        'wins': wins,
        'podiums': podiums,
        'top10': top10,
        'total_results': total_results,
        'season_stats': season_stats[:5],
        'wins_by_year': list(wins_by_year),
        'team_history': team_history[:10],
        'page_title': rider.name,
    }
    return render(request, 'riders/rider_detail.html', context)


def rider_compare(request):
    rider1_slug = request.GET.get('rider1', '')
    rider2_slug = request.GET.get('rider2', '')
    rider1 = None
    rider2 = None
    comparison = None

    if rider1_slug:
        try:
            rider1 = Rider.objects.get(slug=rider1_slug)
        except Rider.DoesNotExist:
            pass

    if rider2_slug:
        try:
            rider2 = Rider.objects.get(slug=rider2_slug)
        except Rider.DoesNotExist:
            pass

    if rider1 and rider2:
        def get_stats(rider):
            results = RaceResult.objects.filter(rider=rider, result_type='gc')
            return {
                'wins': results.filter(rank=1).count(),
                'podiums': results.filter(rank__lte=3).count(),
                'top10': results.filter(rank__lte=10).count(),
                'grand_tours': results.filter(race__is_grand_tour=True, rank=1).count(),
                'monuments': results.filter(race__is_monument=True, rank=1).count(),
                'pcs_points': rider.pcs_points,
                'pcs_rank': rider.pcs_rank or 9999,
            }
        comparison = {
            'rider1': get_stats(rider1),
            'rider2': get_stats(rider2),
        }

    all_riders = Rider.objects.filter(is_active=True).order_by('name').values('name', 'slug')[:200]

    context = {
        'rider1': rider1,
        'rider2': rider2,
        'comparison': comparison,
        'all_riders': list(all_riders),
        'rider1_slug': rider1_slug,
        'rider2_slug': rider2_slug,
        'page_title': 'Comparaison de coureurs',
    }
    return render(request, 'riders/rider_compare.html', context)


def rider_fetch(request, slug):
    """Trigger a live fetch of rider data from PCS."""
    try:
        rider = fetch_rider_from_pcs(slug)
        if rider:
            messages.success(request, f"Données de {rider.name} récupérées avec succès.")
            return redirect('riders:rider_detail', slug=slug)
        else:
            messages.error(request, "Impossible de récupérer les données du coureur.")
    except Exception as exc:
        logger.error("Error fetching rider %s: %s", slug, exc)
        messages.error(request, f"Erreur: {exc}")

    return redirect('riders:rider_detail', slug=slug)


def rider_stats_api(request, slug):
    """Return rider stats as JSON for charts."""
    rider = get_object_or_404(Rider, slug=slug)
    wins_by_year = list(
        RaceResult.objects.filter(rider=rider, rank=1)
        .values('year')
        .annotate(count=Count('id'))
        .order_by('year')
    )
    points_by_year = list(
        RaceResult.objects.filter(rider=rider)
        .values('year')
        .annotate(total=Sum('points'))
        .order_by('year')
    )
    return JsonResponse({
        'wins_by_year': wins_by_year,
        'points_by_year': points_by_year,
        'name': rider.name,
    })
