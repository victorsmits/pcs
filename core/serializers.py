from rest_framework import serializers
from riders.models import Rider, RaceResult, RiderSeasonStats
from races.models import Race, Stage
from teams.models import Team, TeamRoster


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id', 'name', 'slug', 'year', 'nationality', 'country_name', 'status', 'points', 'team_rank']


class RiderSerializer(serializers.ModelSerializer):
    current_team_name = serializers.CharField(source='current_team.name', read_only=True, default=None)

    class Meta:
        model = Rider
        fields = [
            'id', 'name', 'slug', 'nationality', 'date_of_birth', 'age',
            'weight', 'height', 'specialty', 'photo_url', 'current_team_name',
            'pcs_points', 'pcs_rank', 'uci_points', 'uci_rank',
            'one_day_wins', 'stage_wins', 'gc_wins', 'grand_tour_wins', 'monument_wins',
            'is_active', 'flag_code',
        ]


class RiderDetailSerializer(RiderSerializer):
    class Meta(RiderSerializer.Meta):
        fields = RiderSerializer.Meta.fields + ['pcs_url', 'uci_id', 'profile_score']


class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = ['id', 'number', 'name', 'date', 'departure', 'arrival', 'distance', 'stage_type', 'elevation_gain']


class RaceSerializer(serializers.ModelSerializer):
    winner_name = serializers.CharField(source='winner.name', read_only=True, default=None)

    class Meta:
        model = Race
        fields = [
            'id', 'name', 'slug', 'year', 'classification', 'circuit', 'country',
            'country_name', 'start_date', 'end_date', 'distance', 'stages_count',
            'is_stage_race', 'is_monument', 'is_grand_tour', 'winner_name', 'flag_code',
        ]


class RaceDetailSerializer(RaceSerializer):
    stages = StageSerializer(many=True, read_only=True)

    class Meta(RaceSerializer.Meta):
        fields = RaceSerializer.Meta.fields + ['edition', 'departure_city', 'arrival_city', 'description', 'stages']


class RaceResultSerializer(serializers.ModelSerializer):
    rider_name = serializers.CharField(source='rider.name', read_only=True)
    rider_slug = serializers.CharField(source='rider.slug', read_only=True)
    race_name = serializers.CharField(source='race.name', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True, default=None)

    class Meta:
        model = RaceResult
        fields = [
            'id', 'rider_name', 'rider_slug', 'race_name', 'team_name',
            'year', 'rank', 'time_gap', 'points', 'uci_points',
            'dnf', 'dns', 'dsq', 'result_type', 'status',
        ]
