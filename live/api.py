"""API JSON live (Phase 0 : squelettes). Implémentée en Phase 3."""
from datetime import date

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from catalog.models import Stage
from live.models import LiveSession


def stage_live_data(request, slug, year, number):
    """État live courant d'une étape (lu depuis la BDD)."""
    stage = get_object_or_404(Stage, race__slug=slug, race__year=year, number=number)
    session = LiveSession.objects.filter(stage=stage).first()
    if not session:
        return JsonResponse({'available': False}, status=404)
    return JsonResponse({
        'available': True,
        'race_status': session.race_status,
        'km_done': session.km_done,
        'km_to_go': session.km_to_go,
        'perc': session.perc,
        'avg_speed': session.avg_speed,
        'finished': session.finished,
        'groups': list(session.groups.values('label', 'gap', 'rider_count', 'profile_pct')),
        'events': list(session.events.values('marker', 'text', 'html')[:30]),
        'updated_at': session.updated_at.isoformat() if session.updated_at else None,
    })


def today_live(request):
    """Liste des sessions live actives du jour (pour le dashboard)."""
    sessions = LiveSession.objects.filter(
        is_active=True, stage__date=date.today()
    ).select_related('stage__race')
    return JsonResponse({'sessions': [
        {
            'race': s.stage.race.name,
            'slug': s.stage.race.slug,
            'year': s.stage.race.year,
            'stage': s.stage.number,
            'race_status': s.race_status,
            'perc': s.perc,
            'km_to_go': s.km_to_go,
        } for s in sessions
    ]})
