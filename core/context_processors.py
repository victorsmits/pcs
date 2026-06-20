from django.conf import settings


def site_context(request):
    """Variables disponibles dans tous les templates."""
    return {
        'SITE_NAME': 'PCS Live',
        'CURRENT_SEASON': settings.CURRENT_SEASON,
    }
