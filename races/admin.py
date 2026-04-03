from django.contrib import admin
from races.models import Race, Stage, StartList


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = ['name', 'year', 'classification', 'circuit', 'country', 'start_date', 'end_date', 'winner']
    list_filter = ['year', 'classification', 'circuit', 'is_grand_tour', 'is_monument']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    raw_id_fields = ['winner', 'winner_team']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 50
    date_hierarchy = 'start_date'


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ['race', 'number', 'date', 'departure', 'arrival', 'distance', 'stage_type', 'winner']
    list_filter = ['stage_type', 'race__year']
    search_fields = ['race__name', 'departure', 'arrival']
    raw_id_fields = ['race', 'winner', 'winner_team', 'leader_after']


@admin.register(StartList)
class StartListAdmin(admin.ModelAdmin):
    list_display = ['race', 'rider', 'team', 'bib_number', 'withdrew']
    search_fields = ['race__name', 'rider__name']
    raw_id_fields = ['race', 'rider', 'team']
