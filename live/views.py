"""Vues live : dashboard du jour + page live d'une étape (réactive)."""
from datetime import date

from django.shortcuts import render, get_object_or_404

from catalog.models import Stage
from catalog import services as catalog_services
from catalog.profile_svg import build_profile_svg
from live.models import LiveSession
from live import services as live_services


def dashboard(request):
    sessions = (LiveSession.objects.filter(is_active=True)
                .select_related('stage__race').order_by('-updated_at'))
    return render(request, 'live/dashboard.html', {
        'sessions': sessions, 'today': date.today(), 'page_title': 'Direct',
    })


def stage_live(request, slug, year, number):
    stage = get_object_or_404(Stage, race__slug=slug, race__year=year, number=number)

    # S'assure d'avoir le profil
    if not stage.elevation_points:
        try:
            catalog_services.sync_stage_detail(stage)
        except Exception:  # noqa: BLE001
            pass

    session = LiveSession.objects.filter(stage=stage).first()
    # Première synchro live à la demande (création si besoin)
    if session is None or session.last_polled_at is None:
        try:
            session = live_services.sync_live_session(stage, force=True)
        except Exception:  # noqa: BLE001
            pass

    profile = build_profile_svg(stage.elevation_points)
    keypoints = (session.raw_data.get('keypoints') if session and session.raw_data else None) or []
    max_km = session.max_km if session else (stage.distance or None)
    climbs = []
    for kp in keypoints:
        km = kp.get('km')
        if km is not None and max_km:
            climbs.append({
                'x': round(km / max_km * 100, 1),
                'name': kp.get('title', ''),
                'category': str(kp.get('category') or ''),
            })

    return render(request, 'live/stage_live.html', {
        'stage': stage, 'race': stage.race, 'session': session,
        'profile': profile, 'climbs': climbs,
        'page_title': f'Live — {stage}',
    })
