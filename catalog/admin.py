from django.contrib import admin, messages

from catalog import models, services


@admin.action(description='Re-synchro détail (force)')
def resync_stage_detail(modeladmin, request, queryset):
    ok = 0
    for stage in queryset:
        try:
            services.sync_stage_detail(stage, force=True)
            ok += 1
        except Exception as e:
            modeladmin.message_user(request, f'Erreur {stage} : {e}', messages.ERROR)
    if ok:
        modeladmin.message_user(request, f'{ok} étape(s) re-synchronisée(s).', messages.SUCCESS)


class StageInline(admin.TabularInline):
    model = models.Stage
    extra = 0
    fields = ('number', 'date', 'departure', 'arrival', 'distance', 'stage_type', 'winner')
    show_change_link = True


@admin.register(models.Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'classification', 'category', 'start_date', 'is_stage_race', 'detail_synced_at')
    list_filter = ('year', 'classification', 'category', 'is_stage_race', 'is_grand_tour')
    search_fields = ('name', 'slug')
    date_hierarchy = 'start_date'
    inlines = [StageInline]
    raw_id_fields = ('winner', 'winner_team')


@admin.register(models.Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ('race', 'number', 'date', 'departure', 'arrival', 'distance', 'stage_type', 'winner')
    list_filter = ('stage_type', 'date')
    search_fields = ('race__name', 'departure', 'arrival')
    raw_id_fields = ('race', 'winner', 'winner_team')
    actions = [resync_stage_detail]


@admin.register(models.Rider)
class RiderAdmin(admin.ModelAdmin):
    list_display = ('name', 'nationality', 'current_team', 'birthdate', 'detail_synced_at')
    search_fields = ('name', 'slug')
    raw_id_fields = ('current_team',)


@admin.register(models.Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'level', 'nationality', 'detail_synced_at')
    list_filter = ('year', 'level')
    search_fields = ('name', 'slug')


@admin.register(models.Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('race', 'stage', 'classification', 'rank', 'rider', 'team', 'time_gap')
    list_filter = ('classification', 'status')
    search_fields = ('rider__name', 'race__name')
    raw_id_fields = ('race', 'stage', 'rider', 'team')


admin.site.register(models.Climb)
admin.site.register(models.Membership)
admin.site.register(models.StartListEntry)
admin.site.register(models.Ranking)

admin.site.site_header = 'PCS Live — Administration'
admin.site.site_title = 'PCS Live'
admin.site.index_title = 'Supervision'
