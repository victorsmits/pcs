from django.contrib import admin

from .models import DataConflict, IngestionRun, SourceObservation


@admin.register(IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
    list_display = ('provider', 'capability', 'resource_key', 'status', 'records_received', 'records_created', 'records_updated', 'conflicts_created', 'started_at')
    list_filter = ('status', 'provider', 'capability')
    search_fields = ('resource_key', 'error', 'correlation_id')


@admin.register(SourceObservation)
class SourceObservationAdmin(admin.ModelAdmin):
    list_display = ('provider', 'entity_type', 'external_id', 'canonical_model', 'canonical_id', 'observed_at', 'confidence')
    list_filter = ('provider', 'entity_type')
    search_fields = ('external_id', 'canonical_model', 'canonical_id')


@admin.register(DataConflict)
class DataConflictAdmin(admin.ModelAdmin):
    list_display = ('entity_type', 'field_name', 'status', 'reason', 'created_at')
    list_filter = ('status', 'entity_type', 'field_name')
    search_fields = ('canonical_model', 'canonical_id', 'reason')
