"""Vues live (Phase 0 : squelettes). Implémentées en Phase 3."""
from datetime import date

from django.shortcuts import render, get_object_or_404

from catalog.models import Stage


def dashboard(request):
    """Dashboard listant toutes les courses live du jour."""
    return render(request, 'live/dashboard.html', {'page_title': 'Direct', 'today': date.today()})


def stage_live(request, slug, year, number):
    """Page live d'une étape."""
    stage = get_object_or_404(Stage, race__slug=slug, race__year=year, number=number)
    return render(request, 'live/stage_live.html', {
        'stage': stage, 'race': stage.race, 'page_title': f'Live — {stage}',
    })
