from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from riders.models import Rider, RaceResult
from races.models import Race, Stage
from teams.models import Team
from core.serializers import (
    RiderSerializer, RiderDetailSerializer,
    RaceSerializer, RaceDetailSerializer,
    TeamSerializer, RaceResultSerializer,
)


class RiderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Rider.objects.select_related('current_team').all()
    serializer_class = RiderSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['nationality', 'specialty', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'pcs_rank', 'pcs_points', 'uci_rank']
    ordering = ['pcs_rank', 'name']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return RiderDetailSerializer
        return RiderSerializer

    @action(detail=True, url_path='results')
    def results(self, request, pk=None):
        rider = self.get_object()
        year = request.query_params.get('year')
        qs = RaceResult.objects.filter(rider=rider).select_related('race', 'team').order_by('-year', 'rank')
        if year:
            qs = qs.filter(year=year)
        serializer = RaceResultSerializer(qs[:100], many=True)
        return Response(serializer.data)


class RaceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Race.objects.select_related('winner', 'winner_team').all()
    serializer_class = RaceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['year', 'classification', 'is_grand_tour', 'is_monument']
    search_fields = ['name', 'country_name']
    ordering_fields = ['start_date', 'name', 'year']
    ordering = ['-start_date']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return RaceDetailSerializer
        return RaceSerializer

    @action(detail=True, url_path='results')
    def results(self, request, pk=None):
        race = self.get_object()
        qs = RaceResult.objects.filter(race=race, result_type='gc').select_related('rider', 'team').order_by('rank')
        serializer = RaceResultSerializer(qs[:100], many=True)
        return Response(serializer.data)


class TeamViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['year', 'status', 'nationality']
    search_fields = ['name', 'country_name']
    ordering_fields = ['name', 'year', 'points']
    ordering = ['-year', 'name']


class RaceResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RaceResult.objects.select_related('rider', 'race', 'team').all()
    serializer_class = RaceResultSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['rider', 'race', 'year', 'rank', 'result_type']
    ordering_fields = ['year', 'rank']
    ordering = ['-year', 'rank']
