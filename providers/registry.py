from __future__ import annotations

from dataclasses import dataclass, field

from django.conf import settings

from .exceptions import ProviderDisabled, ProviderError
from .interfaces import CyclingProvider


@dataclass
class ProviderRegistry:
    _providers: dict[str, CyclingProvider] = field(default_factory=dict)

    def register(self, provider: CyclingProvider) -> None:
        if provider.key in self._providers:
            raise ProviderError(f'provider already registered: {provider.key}')
        self._providers[provider.key] = provider

    def __contains__(self, key: str) -> bool:
        return key in self._providers

    def get(self, key: str, *, require_enabled: bool = True) -> CyclingProvider:
        provider = self._providers[key]
        if require_enabled and key not in set(settings.PROVIDERS_ENABLED):
            raise ProviderDisabled(f'{key} is disabled')
        return provider

    def enabled(self) -> list[CyclingProvider]:
        enabled = set(settings.PROVIDERS_ENABLED)
        return [p for k, p in self._providers.items() if k in enabled]


registry = ProviderRegistry()
