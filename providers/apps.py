from django.apps import AppConfig


class ProvidersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'providers'
    verbose_name = 'Fournisseurs de données'

    def ready(self):
        from providers.registry import registry
        from providers.fixture import FixtureProvider
        from providers.manual import ManualProvider
        from providers.seed import SeedProvider

        for provider in (SeedProvider(), ManualProvider(), FixtureProvider()):
            if provider.key not in registry:
                registry.register(provider)
