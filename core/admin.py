from django.contrib import admin

from core.models import SyncLog


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'entity_type', 'ref', 'status', 'duration_ms')
    list_filter = ('status', 'entity_type', 'created_at')
    search_fields = ('ref', 'message')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)

    def has_add_permission(self, request):
        return False
