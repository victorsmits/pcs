from django.contrib import admin

from .models import ManualProviderRecord, Provider, ProviderEntityMapping, ProviderRequestLog, ProviderSnapshot


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ('key', 'name', 'provider_type', 'enabled', 'health_status', 'last_success_at', 'last_failure_at')
    list_filter = ('enabled', 'provider_type', 'health_status')
    search_fields = ('key', 'name', 'base_url')


@admin.register(ProviderEntityMapping)
class ProviderEntityMappingAdmin(admin.ModelAdmin):
    list_display = ('provider', 'entity_type', 'external_id', 'canonical_model', 'canonical_id', 'confidence')
    list_filter = ('provider', 'entity_type')
    search_fields = ('external_id', 'canonical_model', 'external_url')


@admin.register(ProviderSnapshot)
class ProviderSnapshotAdmin(admin.ModelAdmin):
    list_display = ('provider', 'capability', 'resource_type', 'resource_key', 'observed_at', 'valid')
    list_filter = ('provider', 'capability', 'resource_type', 'valid')
    search_fields = ('resource_key', 'payload_hash')


@admin.register(ProviderRequestLog)
class ProviderRequestLogAdmin(admin.ModelAdmin):
    list_display = ('provider', 'method', 'url', 'status_code', 'duration_ms', 'success', 'created_at')
    list_filter = ('provider', 'success', 'status_code')
    search_fields = ('url', 'error')


@admin.register(ManualProviderRecord)
class ManualProviderRecordAdmin(admin.ModelAdmin):
    list_display = ('capability', 'resource_key', 'active', 'author', 'updated_at')
    list_filter = ('capability', 'active')
    search_fields = ('resource_key', 'author', 'justification')
