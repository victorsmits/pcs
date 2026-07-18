import hashlib
import json
from typing import Any

from .models import Provider, ProviderSnapshot


def snapshot_payload_hash(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def create_snapshot(*, provider: Provider, capability: str, resource_type: str, resource_key: str, observed_at, payload: Any, valid=True, error='') -> ProviderSnapshot:
    return ProviderSnapshot.objects.create(
        provider=provider,
        capability=capability,
        resource_type=resource_type,
        resource_key=resource_key,
        observed_at=observed_at,
        payload=payload,
        payload_hash=snapshot_payload_hash(payload),
        valid=valid,
        error=error,
    )
