from django.urls import path

from live import views

app_name = 'live'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('race/<pcsslug:slug>/<int:year>/stage/<int:number>/', views.stage_live, name='stage_live'),
]
