from django.urls import path
from races import views

app_name = 'races'

urlpatterns = [
    path('', views.race_list, name='race_list'),
    path('live/', views.live_dashboard, name='live_dashboard'),
    path('calendar/', views.race_calendar, name='race_calendar'),
    path('<slug:slug>/<int:year>/', views.race_detail, name='race_detail'),
    path('<slug:slug>/<int:year>/stages/', views.stage_list, name='stage_list'),
    path('<slug:slug>/<int:year>/stages/<int:stage_num>/', views.stage_detail, name='stage_detail'),
    path('<slug:slug>/<int:year>/fetch/', views.race_fetch, name='race_fetch'),
    path('<slug:slug>/<int:year>/live/', views.race_live_api, name='race_live_api'),
]
