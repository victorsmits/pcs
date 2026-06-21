from django.urls import path, register_converter

from catalog import views
from core.converters import PCSSlugConverter

register_converter(PCSSlugConverter, 'pcsslug')

app_name = 'catalog'

urlpatterns = [
    path('', views.home, name='home'),
    path('search/', views.search, name='search'),
    path('api/search/', views.search_api, name='search_api'),
    path('calendar/', views.calendar, name='calendar'),
    path('races/', views.race_list, name='race_list'),
    path('riders/', views.rider_list, name='rider_list'),
    path('teams/', views.team_list, name='team_list'),
    path('rankings/', views.rankings, name='rankings'),
    path('rider/<pcsslug:slug>/', views.rider_detail, name='rider_detail'),
    path('team/<pcsslug:slug>/<int:year>/', views.team_detail, name='team_detail'),
    path('race/<pcsslug:slug>/<int:year>/', views.race_detail, name='race_detail'),
    path('race/<pcsslug:slug>/<int:year>/go-live/', views.race_go_live, name='race_go_live'),
    path('race/<pcsslug:slug>/<int:year>/history.json', views.race_history, name='race_history'),
    path('race/<pcsslug:slug>/<int:year>/stage/<int:number>/', views.stage_detail, name='stage_detail'),
]
