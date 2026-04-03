import logging
from datetime import date, timedelta
from django.shortcuts import render, redirect
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.http import JsonResponse

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

    ongoing_races = Race.objects.filter(
        start_date__lte=date.today(),
        end_date__gte=date.today(),
        year=current_year
    ).order_by('start_date')[:3]

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
