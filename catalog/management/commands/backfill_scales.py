"""Renseigne l'échelle (min/max altitude) des profils image déjà extraits.

Usage : `python manage.py backfill_scales [--limit N] [--all]`
Nécessite Tesseract (sinon rien n'est renseigné, sans erreur).
"""
from django.core.management.base import BaseCommand

from catalog.models import Stage
from catalog import services


class Command(BaseCommand):
    help = "Calcule l'échelle d'altitude des profils image sans graduations."

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=200)
        parser.add_argument('--all', action='store_true',
                            help='Recalcule aussi les profils ayant déjà une échelle.')

    def handle(self, *args, **opts):
        qs = Stage.objects.exclude(profile_image_url='').filter(profile_from_image=True)
        if not opts['all']:
            qs = qs.filter(min_elevation__isnull=True)
        qs = qs.order_by('-id')[:opts['limit']]

        done = checked = 0
        for stage in qs:
            checked += 1
            try:
                if services.backfill_profile_scale(stage, force=opts['all']):
                    done += 1
                    self.stdout.write(f'  ✓ {stage}  {stage.min_elevation}–{stage.max_elevation} m')
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f'  ✗ {stage} : {exc}')
        self.stdout.write(self.style.SUCCESS(
            f'Échelles renseignées : {done}/{checked}.'))
