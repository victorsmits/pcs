from django.contrib import admin

from live.models import LiveSession, LiveGroup, LiveEvent


class LiveGroupInline(admin.TabularInline):
    model = LiveGroup
    extra = 0


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ('stage', 'race_status', 'is_active', 'km_done', 'km_to_go',
                    'avg_speed', 'finished', 'last_polled_at')
    list_filter = ('race_status', 'is_active', 'finished')
    search_fields = ('stage__race__name',)
    actions = ('activate', 'deactivate')
    inlines = [LiveGroupInline]
    raw_id_fields = ('stage',)

    @admin.action(description='Activer le suivi live')
    def activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description='Suspendre le suivi live')
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(LiveEvent)
class LiveEventAdmin(admin.ModelAdmin):
    list_display = ('session', 'seqnr', 'marker', 'kind', 'created_at')
    search_fields = ('text',)
    raw_id_fields = ('session',)
