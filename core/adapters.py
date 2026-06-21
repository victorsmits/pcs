"""Adapter allauth : restreint la connexion Google aux emails admin autorisés
et leur accorde l'accès staff/superuser."""
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings


def _allowed(email):
    return (email or '').lower() in settings.ADMIN_EMAILS


def _grant(user):
    if _allowed(user.email) and not (user.is_staff and user.is_superuser):
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=['is_staff', 'is_superuser'])


class AdminSocialAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return _allowed(sociallogin.user.email)

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        _grant(user)
        return user

    def pre_social_login(self, request, sociallogin):
        # Connexion d'un compte déjà existant : on (re)confirme les droits admin.
        if sociallogin.is_existing:
            _grant(sociallogin.user)
        super().pre_social_login(request, sociallogin)
