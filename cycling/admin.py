from django.contrib import admin

from .models import Race, RaceResult, Rider, Stage, StartEntry, Team


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = ("name", "year", "classification", "is_grand_tour", "winner")
    list_filter = ("year", "classification", "is_grand_tour", "is_monument")
    search_fields = ("name", "slug")


@admin.register(Rider)
class RiderAdmin(admin.ModelAdmin):
    list_display = ("name", "nationality", "pcs_rank", "current_team")
    list_filter = ("nationality", "specialty", "is_active")
    search_fields = ("name", "slug")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "year", "status", "nationality")
    list_filter = ("year", "status")
    search_fields = ("name", "slug")


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("race", "number", "date", "stage_type", "winner")
    list_filter = ("stage_type",)
    search_fields = ("race__name",)


@admin.register(RaceResult)
class RaceResultAdmin(admin.ModelAdmin):
    list_display = ("race", "rider", "result_type", "rank")
    list_filter = ("result_type", "year")
    search_fields = ("race__name", "rider__name")


@admin.register(StartEntry)
class StartEntryAdmin(admin.ModelAdmin):
    list_display = ("race", "rider", "bib_number", "withdrew")
    search_fields = ("race__name", "rider__name")
