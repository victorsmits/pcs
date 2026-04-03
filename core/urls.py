from django.urls import path
from core import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('search/', views.search, name='search'),
    path('search/autocomplete/', views.search_autocomplete, name='search_autocomplete'),
    path('about/', views.about, name='about'),
    path('stats/', views.stats_overview, name='stats'),
]
