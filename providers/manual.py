from __future__ import annotations

from django.utils import timezone

from .capabilities import ProviderCapability
from .interfaces import ProviderBatch, CyclingProvider
from .models import ManualProviderRecord


class ManualProvider(CyclingProvider):
    key = 'manual'
    capabilities = frozenset({ProviderCapability.RACE_SERIES})

    def fetch_race_series(self) -> ProviderBatch:
        self._require(ProviderCapability.RACE_SERIES)
        records = tuple(
            ManualProviderRecord.objects.filter(active=True, capability=ProviderCapability.RACE_SERIES.value)
            .order_by('resource_key')
            .values_list('payload', flat=True)
        )
        return ProviderBatch(
            provider_key=self.key,
            capability=ProviderCapability.RACE_SERIES,
            observed_at=timezone.now(),
            records=records,
            raw_snapshot={'source': 'manual_provider_records'},
        )
