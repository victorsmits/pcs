from __future__ import annotations

from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from providers.capabilities import ProviderCapability
from providers.interfaces import ProviderBatch
from providers.models import Provider
from providers.registry import registry

from .dto import NormalizedDTO
from .merge import MergeEngine
from .models import IngestionRun, IngestionStatus


class IngestionOrchestrator:
    def sync_batch(self, *, provider: Provider, batch: ProviderBatch, resource_type: str = '', resource_key: str = '') -> IngestionRun:
        run = IngestionRun.objects.create(
            provider=provider,
            capability=batch.capability.value,
            resource_type=resource_type,
            resource_key=resource_key,
            correlation_id=uuid4(),
            records_received=len(batch.records),
        )
        engine = MergeEngine(provider, run)
        try:
            with transaction.atomic():
                for dto in batch.records:
                    if not isinstance(dto, NormalizedDTO):
                        raise TypeError('provider batch items must be NormalizedDTO instances')
                    result = engine.ingest(dto)
                    run.records_created += int(result.created)
                    run.records_updated += int(result.updated)
                    run.conflicts_created += result.conflicts
                run.status = IngestionStatus.SUCCESS
        except Exception as exc:
            run.status = IngestionStatus.FAILED
            run.error = str(exc)
            raise
        finally:
            run.finished_at = timezone.now()
            run.save()
        return run

    def sync_provider_capability(self, *, provider_key: str, capability: ProviderCapability, query=None) -> IngestionRun:
        runtime_provider = registry.get(provider_key)
        provider = Provider.objects.get(key=provider_key)
        method_name = {
            ProviderCapability.CALENDAR: 'fetch_calendar',
            ProviderCapability.RACE_EDITIONS: 'fetch_race_edition',
            ProviderCapability.STAGES: 'fetch_stages',
            ProviderCapability.STARTLIST: 'fetch_startlist',
            ProviderCapability.RESULTS: 'fetch_results',
            ProviderCapability.LIVE_STATE: 'fetch_live',
        }.get(capability)
        if not method_name:
            raise NotImplementedError(f'No orchestrator method for {capability.value}')
        batch = getattr(runtime_provider, method_name)(query)
        return self.sync_batch(provider=provider, batch=batch, resource_type=capability.value)
