"""Crée les planifications Celery Beat par défaut (éditables ensuite dans l'admin)."""
import json

from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    help = 'Initialise les tâches périodiques Beat (discover/poll live, sync calendrier).'

    def handle(self, *args, **opts):
        # Intervalle 15s pour le poll live
        poll_iv, _ = IntervalSchedule.objects.get_or_create(
            every=15, period=IntervalSchedule.SECONDS)
        # Intervalle 10min pour la découverte
        disc_iv, _ = IntervalSchedule.objects.get_or_create(
            every=10, period=IntervalSchedule.MINUTES)
        # Intervalle 6h pour l'upgrade des profils-image
        prof_iv, _ = IntervalSchedule.objects.get_or_create(
            every=6, period=IntervalSchedule.HOURS)
        # Cron quotidien pour le calendrier (04:00)
        cal_cron, _ = CrontabSchedule.objects.get_or_create(
            minute='0', hour='4', day_of_week='*', day_of_month='*', month_of_year='*')

        tasks = [
            ('live: poll sessions actives', 'live.tasks.poll_active_sessions', {'interval': poll_iv}),
            ('live: découverte du jour', 'live.tasks.discover_today', {'interval': disc_iv}),
            ('catalog: sync calendrier', 'catalog.tasks.sync_calendar_year', {'crontab': cal_cron}),
            ('catalog: upgrade profils image', 'catalog.tasks.resync_image_profiles', {'interval': prof_iv}),
            ('catalog: échelle profils image', 'catalog.tasks.backfill_profile_scales', {'interval': prof_iv}),
        ]
        for name, task, sched in tasks:
            PeriodicTask.objects.update_or_create(
                name=name, defaults={'task': task, 'enabled': True, **sched})
            self.stdout.write(self.style.SUCCESS(f'  ✓ {name} → {task}'))
        self.stdout.write(self.style.SUCCESS('Planifications Beat initialisées.'))
