import os

from django.conf import settings


def _css_version():
    try:
        return str(int(os.path.getmtime(settings.BASE_DIR / 'static' / 'css' / 'app.css')))
    except OSError:
        return '1'


def site_context(request):
    """Variables disponibles dans tous les templates."""
    return {
        'SITE_NAME': 'PCS Live',
        'CURRENT_SEASON': settings.CURRENT_SEASON,
        'CSS_VERSION': _css_version(),
    }
