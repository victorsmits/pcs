from django.urls import path
from teams import views

app_name = 'teams'

urlpatterns = [
    path('', views.team_list, name='team_list'),
    path('<slug:slug>/<int:year>/', views.team_detail, name='team_detail'),
    path('<slug:slug>/<int:year>/fetch/', views.team_fetch, name='team_fetch'),
]
