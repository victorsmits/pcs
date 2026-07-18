import uuid

from django.db import models

from providers.models import Provider, ProviderSnapshot


class IngestionStatus(models.TextChoices):
    PENDING = 'pending', 'En attente'
    SUCCESS = 'success', 'Succès'
    FAILED = 'failed', 'Échec'
    PARTIAL = 'partial', 'Partiel'


class ConflictStatus(models.TextChoices):
    OPEN = 'open', 'Ouvert'
    RESOLVED = 'resolved', 'Résolu'
    IGNORED = 'ignored', 'Ignoré'


class IngestionRun(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='ingestion_runs')
    capability = models.CharField(max_length=40)
    resource_type = models.CharField(max_length=80, blank=True)
    resource_key = models.CharField(max_length=255, blank=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    status = models.CharField(max_length=20, choices=IngestionStatus.choices, default=IngestionStatus.PENDING)
    records_received = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    conflicts_created = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [models.Index(fields=['provider', 'capability']), models.Index(fields=['status']), models.Index(fields=['correlation_id'])]


class SourceObservation(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    run = models.ForeignKey(IngestionRun, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='source_observations')
    snapshot = models.ForeignKey(ProviderSnapshot, on_delete=models.SET_NULL, null=True, blank=True, related_name='observations')
    entity_type = models.CharField(max_length=60)
    external_id = models.CharField(max_length=255)
    external_url = models.URLField(blank=True, max_length=600)
    canonical_model = models.CharField(max_length=100, blank=True)
    canonical_id = models.PositiveBigIntegerField(null=True, blank=True)
    observed_at = models.DateTimeField()
    source_updated_at = models.DateTimeField(null=True, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=1)
    payload_version = models.CharField(max_length=40, default='1')
    normalized_payload = models.JSONField(default=dict, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['canonical_model', 'canonical_id']), models.Index(fields=['entity_type', 'external_id'])]


class DataConflict(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    entity_type = models.CharField(max_length=60)
    canonical_model = models.CharField(max_length=100, blank=True)
    canonical_id = models.PositiveBigIntegerField(null=True, blank=True)
    field_name = models.CharField(max_length=120)
    current_value = models.JSONField(default=dict, blank=True)
    incoming_value = models.JSONField(default=dict, blank=True)
    winning_observation = models.ForeignKey(SourceObservation, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    losing_observation = models.ForeignKey(SourceObservation, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=ConflictStatus.choices, default=ConflictStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['entity_type', 'field_name', 'status']), models.Index(fields=['canonical_model', 'canonical_id'])]
