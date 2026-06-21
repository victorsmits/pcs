"""Convertisseurs d'URL personnalisés."""


class PCSSlugConverter:
    """Comme le converter slug mais autorise le point (slugs PCS, ex. 'int.-femminile')."""
    regex = r'[-a-zA-Z0-9_.]+'

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value
