from django.contrib import admin
from riders.models import Rider, RaceResult, RiderSeasonStats


@admin.register(Rider)
class RiderAdmin(admin.ModelAdmin):
    list_display = ['name', 'nationality', 'specialty', 'current_team', 'pcs_rank', 'pcs_points', 'is_active']
    list_filter = ['nationality', 'specialty', 'is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 50
    ordering = ['pcs_rank', 'name']


@admin.register(RaceResult)
class RaceResultAdmin(admin.ModelAdmin):
    list_display = ['rider', 'race', 'year', 'rank', 'result_type', 'points', 'dnf', 'dns']
    list_filter = ['year', 'result_type', 'dnf', 'dns', 'dsq']
    search_fields = ['rider__name', 'race__name']
    raw_id_fields = ['rider', 'race', 'stage', 'team']
    list_per_page = 50


@admin.register(RiderSeasonStats)
class RiderSeasonStatsAdmin(admin.ModelAdmin):
    list_display = ['rider', 'year', 'wins', 'podiums', 'points', 'rank']
    list_filter = ['year']
    search_fields = ['rider__name']
    raw_id_fields = ['rider', 'team']
