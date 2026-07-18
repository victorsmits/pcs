from __future__ import annotations

from celery import shared_task

from providers.capabilities import ProviderCapability

from .orchestrator import IngestionOrchestrator


@shared_task(bind=True, autoretry_for=(), retry_backoff=True)
def sync_provider_capability(self, provider_key: str, capability: str) -> str:
    run = IngestionOrchestrator().sync_provider_capability(
        provider_key=provider_key,
        capability=ProviderCapability(capability),
    )
    return str(run.public_id)
