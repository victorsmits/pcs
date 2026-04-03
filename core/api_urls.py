from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core import api_views

router = DefaultRouter()
router.register(r'riders', api_views.RiderViewSet, basename='rider')
router.register(r'races', api_views.RaceViewSet, basename='race')
router.register(r'teams', api_views.TeamViewSet, basename='team')
router.register(r'results', api_views.RaceResultViewSet, basename='result')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
]
