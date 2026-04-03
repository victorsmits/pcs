from django.contrib import admin
from rankings.models import RiderRanking, TeamRanking


@admin.register(RiderRanking)
class RiderRankingAdmin(admin.ModelAdmin):
    list_display = ['rank', 'rider', 'ranking_type', 'year', 'points', 'team']
    list_filter = ['ranking_type', 'year']
    search_fields = ['rider__name']
    raw_id_fields = ['rider', 'team']
    list_per_page = 100
    ordering = ['rank']


@admin.register(TeamRanking)
class TeamRankingAdmin(admin.ModelAdmin):
    list_display = ['rank', 'team', 'ranking_type', 'year', 'points', 'wins']
    list_filter = ['ranking_type', 'year']
    search_fields = ['team__name']
    raw_id_fields = ['team']
    list_per_page = 100
    ordering = ['rank']
