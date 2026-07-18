import uuid

from django.db import models


class ProviderType(models.TextChoices):
    OFFICIAL_GOVERNING_BODY = 'official_governing_body', 'Instance officielle'
    OFFICIAL_ORGANIZER = 'official_organizer', 'Organisateur officiel'
    OFFICIAL_TIMING = 'official_timing', 'Chronométrage officiel'
    NATIONAL_FEDERATION = 'national_federation', 'Fédération nationale'
    LICENSED_COMMERCIAL = 'licensed_commercial', 'Commercial licencié'
    COMMUNITY = 'community', 'Communautaire'
    MANUAL = 'manual', 'Manuel'
    FIXTURE = 'fixture', 'Fixture'
    LEGACY = 'legacy', 'Legacy'


class ProviderAuthority(models.TextChoices):
    MANUAL_OVERRIDE = 'manual_override', 'Correction manuelle'
    OFFICIAL = 'official', 'Officiel'
    LICENSED = 'licensed', 'Licencié'
    COMMUNITY = 'community', 'Communautaire'
    LEGACY = 'legacy', 'Legacy'
    UNKNOWN = 'unknown', 'Inconnu'


class ProviderHealthStatus(models.TextChoices):
    UNKNOWN = 'unknown', 'Inconnu'
    HEALTHY = 'healthy', 'Sain'
    DEGRADED = 'degraded', 'Dégradé'
    DOWN = 'down', 'Indisponible'
    DISABLED = 'disabled', 'Désactivé'


class Provider(models.Model):
    key = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    provider_type = models.CharField(max_length=40, choices=ProviderType.choices)
    enabled = models.BooleanField(default=False)
    base_url = models.URLField(blank=True, max_length=500)
    capabilities = models.JSONField(default=list, blank=True)
    authority_level = models.CharField(max_length=30, choices=ProviderAuthority.choices, default=ProviderAuthority.UNKNOWN)
    attribution_text = models.CharField(max_length=255, blank=True)
    terms_url = models.URLField(blank=True, max_length=500)
    license_metadata = models.JSONField(default=dict, blank=True)
    credential_env_prefix = models.CharField(max_length=80, blank=True)
    default_cache_ttl = models.PositiveIntegerField(default=3600)
    min_request_interval_seconds = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    max_requests_per_minute = models.PositiveIntegerField(null=True, blank=True)
    health_status = models.CharField(
        max_length=20, choices=ProviderHealthStatus.choices, default=ProviderHealthStatus.UNKNOWN
    )
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']
        indexes = [models.Index(fields=['enabled']), models.Index(fields=['provider_type']), models.Index(fields=['health_status'])]

    def __str__(self):
        return self.name


class ProviderEntityMapping(models.Model):
    class EntityType(models.TextChoices):
        RIDER = 'rider', 'Coureur'
        TEAM = 'team', 'Équipe'
        TEAM_IDENTITY = 'team_identity', "Identité d'équipe"
        RACE_SERIES = 'race_series', 'Série'
        RACE_EDITION = 'race_edition', 'Édition'
        STAGE = 'stage', 'Étape'
        LIVE_SESSION = 'live_session', 'Session live'
        RESULT = 'result', 'Résultat'

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='entity_mappings')
    entity_type = models.CharField(max_length=40, choices=EntityType.choices)
    external_id = models.CharField(max_length=255)
    external_url = models.URLField(blank=True, max_length=600)
    canonical_model = models.CharField(max_length=100)
    canonical_id = models.PositiveBigIntegerField()
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=1)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [('provider', 'entity_type', 'external_id')]
        indexes = [models.Index(fields=['canonical_model', 'canonical_id']), models.Index(fields=['entity_type', 'external_id'])]


class ProviderSnapshot(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='snapshots')
    capability = models.CharField(max_length=40)
    resource_type = models.CharField(max_length=80)
    resource_key = models.CharField(max_length=255, blank=True)
    observed_at = models.DateTimeField()
    source_updated_at = models.DateTimeField(null=True, blank=True)
    payload_version = models.CharField(max_length=40, default='1')
    payload_hash = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    valid = models.BooleanField(default=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['provider', 'capability', 'resource_key']), models.Index(fields=['observed_at'])]


class ProviderRequestLog(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='request_logs')
    capability = models.CharField(max_length=40, blank=True)
    url = models.URLField(max_length=700)
    method = models.CharField(max_length=10, default='GET')
    status_code = models.PositiveIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    cache_hit = models.BooleanField(default=False)
    success = models.BooleanField(default=False)
    error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['provider', 'created_at']), models.Index(fields=['success'])]


class ManualProviderRecord(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    capability = models.CharField(max_length=40)
    resource_key = models.CharField(max_length=255)
    payload = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    author = models.CharField(max_length=150, blank=True)
    justification = models.TextField(blank=True)
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['capability', 'resource_key']
        indexes = [models.Index(fields=['capability', 'active']), models.Index(fields=['resource_key'])]
