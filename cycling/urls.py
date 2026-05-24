from django.urls import path
from cycling import views

app_name = 'cycling'

urlpatterns = [
    path('', views.home, name='home'),
    # Races
    path('races/', views.race_list, name='race_list'),
    path('races/live/', views.live_dashboard, name='live_dashboard'),
    path('races/<slug:slug>/<int:year>/', views.race_detail, name='race_detail'),
    path('races/<slug:slug>/<int:year>/stage/<int:stage_num>/', views.stage_detail, name='stage_detail'),
    # HTMX fragment endpoints (polled every 30s for live races)
    path('races/<slug:slug>/<int:year>/htmx/gc/', views.gc_fragment, name='gc_fragment'),
    path('races/<slug:slug>/<int:year>/htmx/stage/<int:stage_num>/', views.stage_results_fragment, name='stage_results_fragment'),
    path('races/<slug:slug>/<int:year>/htmx/live-bar/', views.live_bar_fragment, name='live_bar_fragment'),
    # Riders
    path('riders/', views.rider_list, name='rider_list'),
    path('riders/<slug:slug>/', views.rider_detail, name='rider_detail'),
    # Teams
    path('teams/', views.team_list, name='team_list'),
    path('teams/<slug:slug>/<int:year>/', views.team_detail, name='team_detail'),
    # Search
    path('search/', views.search, name='search'),
    path('search/autocomplete/', views.search_autocomplete, name='search_autocomplete'),
    # Misc
    path('about/', views.about, name='about'),
    # Admin sync
    path('sync/', views.sync_page, name='sync'),
    path('sync/<str:job_id>/status/', views.sync_status_api, name='sync_status'),
]
