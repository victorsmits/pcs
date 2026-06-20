from django.urls import path

from catalog import views

app_name = 'catalog'

urlpatterns = [
    path('', views.home, name='home'),
    path('calendar/', views.calendar, name='calendar'),
    path('races/', views.race_list, name='race_list'),
    path('riders/', views.rider_list, name='rider_list'),
    path('teams/', views.team_list, name='team_list'),
    path('rankings/', views.rankings, name='rankings'),
    path('rider/<slug:slug>/', views.rider_detail, name='rider_detail'),
    path('team/<slug:slug>/<int:year>/', views.team_detail, name='team_detail'),
    path('race/<slug:slug>/<int:year>/', views.race_detail, name='race_detail'),
    path('race/<slug:slug>/<int:year>/stage/<int:number>/', views.stage_detail, name='stage_detail'),
]
