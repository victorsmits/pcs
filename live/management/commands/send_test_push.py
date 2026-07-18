"""Envoie une notification push de test (vérification de bout en bout).

Usage :
    python manage.py send_test_push                 # à tous les abonnés
    python manage.py send_test_push --endpoint URL   # à un appareil précis
    python manage.py send_test_push --race tour-de-france --year 2026  # aux abonnés d'une course
"""
from django.core.management.base import BaseCommand

from live.models import PushSubscription
from live import push


class Command(BaseCommand):
    help = 'Envoie une notification push de test aux abonnés.'

    def add_arguments(self, parser):
        parser.add_argument('--endpoint', help='Limiter à cet endpoint d\'abonnement.')
        parser.add_argument('--race', help='Limiter aux abonnés de cette course (slug).')
        parser.add_argument('--year', type=int)
        parser.add_argument('--title', default='Test — PCS Live')
        parser.add_argument('--body', default='Notification de test : tout fonctionne ✅')

    def handle(self, *args, **opts):
        if not push.push_enabled():
            self.stderr.write(self.style.ERROR(
                'Push désactivé : VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY manquantes.'))
            return

        subs = PushSubscription.objects.all()
        if opts['endpoint']:
            subs = subs.filter(endpoint=opts['endpoint'])
        if opts['race']:
            subs = subs.filter(follows__race__slug=opts['race'])
            if opts['year']:
                subs = subs.filter(follows__race__year=opts['year'])
            subs = subs.distinct()

        total = subs.count()
        if not total:
            self.stdout.write(self.style.WARNING('Aucun abonnement correspondant.'))
            return

        sent = push.send_to_subscriptions(
            subs, title=opts['title'], body=opts['body'], url='/', tag='test')
        self.stdout.write(self.style.SUCCESS(
            f'Notification envoyée à {sent}/{total} abonnement(s).'))
