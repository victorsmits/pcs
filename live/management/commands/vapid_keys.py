"""Génère une paire de clés VAPID pour les notifications Web Push.

Usage : `python manage.py vapid_keys`
Copier les deux valeurs dans les variables d'environnement de production :
    VAPID_PUBLIC_KEY=...   (exposée au navigateur — applicationServerKey)
    VAPID_PRIVATE_KEY=...  (SECRÈTE — utilisée par pywebpush pour signer)
"""
import base64

from django.core.management.base import BaseCommand


def _b64url(raw):
    return base64.urlsafe_b64encode(raw).decode('utf-8').rstrip('=')


class Command(BaseCommand):
    help = 'Génère une paire de clés VAPID (Web Push).'

    def handle(self, *args, **opts):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        priv = ec.generate_private_key(ec.SECP256R1())
        pub_point = priv.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )  # 65 octets (applicationServerKey)
        priv_scalar = priv.private_numbers().private_value.to_bytes(32, 'big')

        self.stdout.write(self.style.SUCCESS('Clés VAPID générées :\n'))
        self.stdout.write(f'VAPID_PUBLIC_KEY={_b64url(pub_point)}')
        self.stdout.write(f'VAPID_PRIVATE_KEY={_b64url(priv_scalar)}')
        self.stdout.write(self.style.WARNING(
            "\nAjoute-les aux variables d'environnement de prod "
            "(la privée reste secrète, jamais commitée)."))
