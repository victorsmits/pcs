from django.contrib import admin
from teams.models import Team, TeamRoster


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'year', 'status', 'nationality', 'wins', 'points', 'team_rank']
    list_filter = ['year', 'status', 'nationality']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 50


@admin.register(TeamRoster)
class TeamRosterAdmin(admin.ModelAdmin):
    list_display = ['rider', 'team', 'role']
    search_fields = ['rider__name', 'team__name']
    raw_id_fields = ['rider', 'team']
    list_filter = ['team__year', 'role']
