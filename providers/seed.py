from __future__ import annotations

from django.utils import timezone

from catalog.seed_services import load_road_series

from .capabilities import ProviderCapability
from .interfaces import ProviderBatch, CyclingProvider


class SeedProvider(CyclingProvider):
    key = 'seed'
    capabilities = frozenset({ProviderCapability.RACE_SERIES})

    def fetch_race_series(self) -> ProviderBatch:
        self._require(ProviderCapability.RACE_SERIES)
        return ProviderBatch(
            provider_key=self.key,
            capability=ProviderCapability.RACE_SERIES,
            observed_at=timezone.now(),
            records=tuple(load_road_series()),
            raw_snapshot={'source': 'catalog/seeds/road_series.yaml'},
        )
