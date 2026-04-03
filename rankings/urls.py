from django.urls import path
from rankings import views

app_name = 'rankings'

urlpatterns = [
    path('', views.individual_rankings, name='individual_rankings'),
    path('teams/', views.team_rankings, name='team_rankings'),
]
