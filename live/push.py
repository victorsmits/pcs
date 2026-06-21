"""Envoi de notifications Web Push (VAPID) aux appareils abonnés.

Dégradation propre : si les clés VAPID ne sont pas configurées (PUSH_ENABLED
faux) ou si pywebpush est absent, les fonctions ne font rien et renvoient 0.
Les abonnements morts (404/410) sont supprimés automatiquement.
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger('live')


def push_enabled():
    return bool(getattr(settings, 'PUSH_ENABLED', False))


def _send_one(sub, payload):
    """Envoie à un abonnement. Renvoie True si OK, False sinon. Supprime si mort."""
    from pywebpush import webpush, WebPushException
    try:
        webpush(
            subscription_info=sub.as_dict(),
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={'sub': f'mailto:{settings.VAPID_ADMIN_EMAIL}'},
            timeout=10,
        )
        return True
    except WebPushException as exc:
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        if status in (404, 410):  # abonnement expiré / révoqué → on nettoie
            sub.delete()
        else:
            logger.warning('Échec push (%s) : %s', status, exc)
        return False
    except Exception as exc:  # noqa: BLE001 — ne jamais casser le moteur live
        logger.warning('Échec push : %s', exc)
        return False


def send_to_subscriptions(subscriptions, *, title, body, url='/', tag=None):
    """Envoie une notification à une liste/queryset d'abonnements."""
    if not push_enabled():
        return 0
    payload = {'title': title, 'body': body, 'url': url}
    if tag:
        payload['tag'] = tag
    sent = 0
    for sub in subscriptions:
        if _send_one(sub, payload):
            sent += 1
    return sent


def notify_race_followers(race, *, title, body, url='/', tag=None):
    """Notifie tous les appareils qui suivent cette course."""
    if not push_enabled():
        return 0
    from live.models import PushSubscription
    subs = (PushSubscription.objects
            .filter(follows__race=race).distinct())
    n = send_to_subscriptions(subs, title=title, body=body, url=url, tag=tag)
    if n:
        logger.info('Push « %s » → %d abonné(s) de %s', title, n, race)
    return n
