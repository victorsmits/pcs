"""Modèles catalogue canoniques et compatibilité legacy additive."""
import uuid

from django.db import models
from django.urls import reverse


# ---------------------------------------------------------------------------
# Choix
# ---------------------------------------------------------------------------
class Classification(models.TextChoices):
    UWT_1 = '1.UWT', '1.UWT'
    UWT_2 = '2.UWT', '2.UWT'
    PRO_1 = '1.Pro', '1.Pro'
    PRO_2 = '2.Pro', '2.Pro'
    E1_1 = '1.1', '1.1'
    E1_2 = '2.1', '2.1'
    E2_1 = '1.2', '1.2'
    E2_2 = '2.2', '2.2'
    WWT_1 = '1.WWT', '1.WWT'
    WWT_2 = '2.WWT', '2.WWT'
    CC = 'CC', 'Championnat continental'
    CN = 'NC', 'Championnat national'
    WC = 'WC', 'Championnat du monde'
    OG = 'OG', 'Jeux olympiques'


class Category(models.TextChoices):
    ME = 'ME', 'Hommes Élite'
    WE = 'WE', 'Femmes Élite'
    MU = 'MU', 'Hommes U23'
    WU = 'WU', 'Femmes U23'
    MJ = 'MJ', 'Hommes Juniors'
    WJ = 'WJ', 'Femmes Juniors'


class StageType(models.TextChoices):
    FLAT = 'flat', 'Plat'
    HILLS_FLAT = 'hills_flat', 'Vallonné (arrivée plate)'
    HILLS_UPHILL = 'hills_uphill', 'Vallonné (arrivée en bosse)'
    MOUNTAINS_FLAT = 'mountains_flat', 'Montagne (arrivée plate)'
    MOUNTAINS_UPHILL = 'mountains_uphill', 'Montagne (arrivée au sommet)'
    ITT = 'itt', 'Contre-la-montre individuel'
    TTT = 'ttt', 'Contre-la-montre par équipes'
    PROLOGUE = 'prologue', 'Prologue'
    UNKNOWN = 'unknown', 'Inconnu'


class ClassificationType(models.TextChoices):
    STAGE = 'stage', 'Étape'
    GC = 'gc', 'Général'
    POINTS = 'points', 'Points'
    KOM = 'kom', 'Montagne'
    YOUTH = 'youth', 'Jeunes'
    TEAMS = 'teams', 'Équipes'


class ResultStatus(models.TextChoices):
    OK = 'ok', 'Classé'
    DNF = 'dnf', 'Abandon'
    DNS = 'dns', 'Non partant'
    OTL = 'otl', 'Hors délai'
    DSQ = 'dsq', 'Disqualifié'


class RaceDiscipline(models.TextChoices):
    ROAD = 'road', 'Route'


class RaceFormat(models.TextChoices):
    ONE_DAY = 'one_day', "Course d'un jour"
    STAGE_RACE = 'stage_race', 'Course par étapes'
    CHAMPIONSHIP_ROAD_RACE = 'championship_road_race', 'Championnat route'
    CHAMPIONSHIP_ITT = 'championship_itt', 'Championnat contre-la-montre'


class RaceScope(models.TextChoices):
    REGULAR = 'regular', 'Régulier'
    WORLD_CHAMPIONSHIP = 'world_championship', 'Championnat du monde'
    CONTINENTAL_CHAMPIONSHIP = 'continental_championship', 'Championnat continental'
    NATIONAL_CHAMPIONSHIP = 'national_championship', 'Championnat national'
    OLYMPIC = 'olympic', 'Jeux olympiques'


class RaceImportance(models.TextChoices):
    P0 = 'P0', 'P0'
    P1 = 'P1', 'P1'
    P2 = 'P2', 'P2'
    P3 = 'P3', 'P3'


class EditionStatus(models.TextChoices):
    SCHEDULED = 'scheduled', 'Planifiée'
    ACTIVE = 'active', 'Active'
    FINISHED = 'finished', 'Terminée'
    CANCELLED = 'cancelled', 'Annulée'
    UNKNOWN = 'unknown', 'Inconnu'


class CanonicalStageKind(models.TextChoices):
    ROAD = 'road', 'Route'
    ITT = 'itt', 'Contre-la-montre individuel'
    TTT = 'ttt', 'Contre-la-montre par équipes'
    PROLOGUE = 'prologue', 'Prologue'
    SPLIT_STAGE = 'split_stage', 'Demi-étape'


# ---------------------------------------------------------------------------
# Coureurs & équipes
# ---------------------------------------------------------------------------
class Rider(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    canonical_slug = models.SlugField(max_length=220, blank=True, db_index=True)
    normalized_name = models.CharField(max_length=220, blank=True, db_index=True)
    gender_category = models.CharField(max_length=2, choices=Category.choices, default=Category.ME)
    metadata = models.JSONField(default=dict, blank=True)
    slug = models.SlugField(max_length=200, unique=True)
    pcs_id = models.IntegerField(null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200)
    nationality = models.CharField(max_length=3, blank=True)  # code ISO2/PCS (be, fr…)
    birthdate = models.DateField(null=True, blank=True)
    weight = models.FloatField(null=True, blank=True)
    height = models.FloatField(null=True, blank=True)
    photo_url = models.URLField(blank=True)
    specialties = models.JSONField(default=dict, blank=True)  # {sprint, climb, tt, ...}
    current_team = models.ForeignKey(
        'Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='current_riders'
    )
    detail_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Coureur'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('catalog:rider_detail', kwargs={'slug': self.slug})


class Team(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    identity = models.ForeignKey(
        'TeamIdentity', on_delete=models.SET_NULL, null=True, blank=True, related_name='seasons'
    )
    slug = models.SlugField(max_length=200)
    year = models.IntegerField()
    pcs_id = models.IntegerField(null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200)
    nationality = models.CharField(max_length=3, blank=True)
    level = models.CharField(max_length=40, blank=True)   # WorldTeam, ProTeam, Continental, Women
    abbreviation = models.CharField(max_length=10, blank=True)
    jersey_url = models.URLField(blank=True)
    detail_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Équipe'
        ordering = ['name']
        unique_together = [('slug', 'year')]
        indexes = [models.Index(fields=['slug', 'year']), models.Index(fields=['year'])]

    def __str__(self):
        return f'{self.name} ({self.year})'

    def get_absolute_url(self):
        return reverse('catalog:team_detail', kwargs={'slug': self.slug, 'year': self.year})


class TeamIdentity(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    canonical_slug = models.SlugField(max_length=220, unique=True)
    current_name = models.CharField(max_length=220)
    primary_country = models.CharField(max_length=3, blank=True)
    aliases = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Identité d'équipe"
        verbose_name_plural = "Identités d'équipe"
        ordering = ['current_name']

    def __str__(self):
        return self.current_name


class Membership(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='memberships')
    rider = models.ForeignKey(Rider, on_delete=models.CASCADE, related_name='memberships')
    year = models.IntegerField()

    class Meta:
        verbose_name = 'Appartenance'
        unique_together = [('team', 'rider', 'year')]
        indexes = [models.Index(fields=['rider', 'year']), models.Index(fields=['team', 'year'])]

    def __str__(self):
        return f'{self.rider} → {self.team} ({self.year})'


# ---------------------------------------------------------------------------
# Courses & étapes
# ---------------------------------------------------------------------------
class RaceSeries(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    canonical_slug = models.SlugField(max_length=220, unique=True)
    current_name = models.CharField(max_length=220)
    gender_category = models.CharField(max_length=2, choices=Category.choices, default=Category.ME)
    discipline = models.CharField(max_length=20, choices=RaceDiscipline.choices, default=RaceDiscipline.ROAD)
    format = models.CharField(max_length=40, choices=RaceFormat.choices, default=RaceFormat.ONE_DAY)
    scope = models.CharField(max_length=40, choices=RaceScope.choices, default=RaceScope.REGULAR)
    primary_country = models.CharField(max_length=3, blank=True)
    importance = models.CharField(max_length=2, choices=RaceImportance.choices, default=RaceImportance.P3)
    active = models.BooleanField(default=True)
    aliases = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Série de course'
        verbose_name_plural = 'Séries de courses'
        ordering = ['current_name']
        indexes = [
            models.Index(fields=['gender_category', 'discipline']),
            models.Index(fields=['scope']),
            models.Index(fields=['importance']),
            models.Index(fields=['active']),
        ]

    def __str__(self):
        return self.current_name


class RaceSeriesAlias(models.Model):
    series = models.ForeignKey(RaceSeries, on_delete=models.CASCADE, related_name='series_aliases')
    name = models.CharField(max_length=220)
    normalized_name = models.CharField(max_length=220, db_index=True)
    valid_from_year = models.IntegerField(null=True, blank=True)
    valid_to_year = models.IntegerField(null=True, blank=True)
    locale = models.CharField(max_length=12, default='und')

    class Meta:
        verbose_name = 'Alias de série'
        verbose_name_plural = 'Alias de séries'
        unique_together = [('series', 'normalized_name', 'valid_from_year', 'valid_to_year', 'locale')]
        indexes = [models.Index(fields=['normalized_name'])]

    def __str__(self):
        return self.name


class Race(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    series = models.ForeignKey(RaceSeries, on_delete=models.SET_NULL, null=True, blank=True, related_name='editions')
    official_name = models.CharField(max_length=220, blank=True)
    status = models.CharField(max_length=20, choices=EditionStatus.choices, default=EditionStatus.UNKNOWN)
    host_country = models.CharField(max_length=3, blank=True)
    start_location = models.CharField(max_length=120, blank=True)
    finish_location = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    slug = models.SlugField(max_length=200)
    year = models.IntegerField()
    pcs_id = models.IntegerField(null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200)
    classification = models.CharField(max_length=10, choices=Classification.choices, blank=True)
    category = models.CharField(max_length=2, choices=Category.choices, default=Category.ME)
    circuit = models.CharField(max_length=60, blank=True)
    country = models.CharField(max_length=3, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    distance = models.FloatField(null=True, blank=True)
    is_stage_race = models.BooleanField(default=False)
    is_grand_tour = models.BooleanField(default=False)
    is_monument = models.BooleanField(default=False)
    edition = models.IntegerField(null=True, blank=True)
    winner = models.ForeignKey(
        Rider, on_delete=models.SET_NULL, null=True, blank=True, related_name='won_races'
    )
    winner_team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='won_races'
    )
    detail_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Course'
        ordering = ['start_date', 'name']
        unique_together = [('slug', 'year')]
        indexes = [
            models.Index(fields=['slug', 'year']),
            models.Index(fields=['year']),
            models.Index(fields=['start_date']),
            models.Index(fields=['classification']),
        ]

    def __str__(self):
        return f'{self.name} {self.year}'

    def get_absolute_url(self):
        return reverse('catalog:race_detail', kwargs={'slug': self.slug, 'year': self.year})


class Stage(models.Model):
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='stages')
    number = models.IntegerField()
    public_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    stage_key = models.CharField(max_length=40, blank=True, db_index=True)
    sequence = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    display_label = models.CharField(max_length=60, blank=True)
    stage_kind = models.CharField(max_length=20, choices=CanonicalStageKind.choices, default=CanonicalStageKind.ROAD)
    route_geometry = models.JSONField(default=dict, blank=True)
    profile_metadata = models.JSONField(default=dict, blank=True)
    name = models.CharField(max_length=200, blank=True)
    date = models.DateField(null=True, blank=True)
    departure = models.CharField(max_length=120, blank=True)
    arrival = models.CharField(max_length=120, blank=True)
    distance = models.FloatField(null=True, blank=True)
    stage_type = models.CharField(max_length=20, choices=StageType.choices, default=StageType.UNKNOWN)
    profile_score = models.IntegerField(null=True, blank=True)
    vertical_meters = models.IntegerField(null=True, blank=True)
    gradient_final = models.FloatField(null=True, blank=True)
    profile_image_url = models.URLField(blank=True, max_length=300)
    map_image_url = models.URLField(blank=True, max_length=300)
    finish_image_url = models.URLField(blank=True, max_length=300)
    min_elevation = models.IntegerField(null=True, blank=True)
    max_elevation = models.IntegerField(null=True, blank=True)
    # Points d'altitude (x%, y%) extraits du clip-path PCS → régénération SVG
    elevation_points = models.JSONField(default=list, blank=True)
    # True si le profil a été reconstruit depuis l'image (à upgrader en vectoriel
    # dès que PCS publie le polygone / les cols).
    profile_from_image = models.BooleanField(default=False)
    winner = models.ForeignKey(
        Rider, on_delete=models.SET_NULL, null=True, blank=True, related_name='stage_wins'
    )
    winner_team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='stage_wins'
    )
    detail_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Étape'
        ordering = ['number']
        unique_together = [('race', 'number')]
        indexes = [models.Index(fields=['race', 'number']), models.Index(fields=['date'])]

    def __str__(self):
        return f'{self.race} — Étape {self.number}'

    def get_absolute_url(self):
        return reverse('catalog:stage_detail', kwargs={
            'slug': self.race.slug, 'year': self.race.year, 'number': self.number,
        })


class Climb(models.Model):
    """Point clé d'une étape : col ou sprint intermédiaire."""

    class Kind(models.TextChoices):
        CLIMB = 'climb', 'Col'
        SPRINT = 'sprint', 'Sprint'

    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name='climbs')
    name = models.CharField(max_length=160)
    km = models.FloatField(null=True, blank=True)
    length = models.FloatField(null=True, blank=True)
    avg_grad = models.FloatField(null=True, blank=True)
    category = models.CharField(max_length=10, blank=True)  # HC, 1, 2, 3, 4
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.CLIMB)
    location_url = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'Point clé'
        ordering = ['km']

    def __str__(self):
        return f'{self.name} ({self.km} km)'


# ---------------------------------------------------------------------------
# Engagés, résultats, maillots, classements
# ---------------------------------------------------------------------------
class StartListEntry(models.Model):
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='startlist')
    public_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, null=True, blank=True, related_name='startlist')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    role = models.CharField(max_length=30, blank=True)
    rider = models.ForeignKey(Rider, on_delete=models.CASCADE, related_name='startlist_entries')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='startlist_entries')
    bib = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ResultStatus.choices, default=ResultStatus.OK)

    class Meta:
        verbose_name = 'Engagé'
        unique_together = [('race', 'rider')]
        indexes = [models.Index(fields=['race']), models.Index(fields=['rider'])]

    def __str__(self):
        return f'{self.rider} — {self.race} (#{self.bib})'


class Result(models.Model):
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='results')
    public_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, null=True, blank=True, related_name='results')
    rider = models.ForeignKey(Rider, on_delete=models.CASCADE, related_name='results')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='results')
    classification = models.CharField(max_length=10, choices=ClassificationType.choices, default=ClassificationType.STAGE)
    rank = models.IntegerField(null=True, blank=True)
    time = models.DurationField(null=True, blank=True)
    elapsed_time_ms = models.BigIntegerField(null=True, blank=True)
    gap_ms = models.BigIntegerField(null=True, blank=True)
    gap_laps = models.IntegerField(null=True, blank=True)
    time_gap = models.CharField(max_length=30, blank=True)
    bonus = models.CharField(max_length=20, blank=True)
    bonus_seconds = models.IntegerField(null=True, blank=True)
    penalty_seconds = models.IntegerField(null=True, blank=True)
    raw_display_time = models.CharField(max_length=60, blank=True)
    points_uci = models.IntegerField(null=True, blank=True)
    points_pcs = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ResultStatus.choices, default=ResultStatus.OK)

    class Meta:
        verbose_name = 'Résultat'
        ordering = ['classification', 'rank']
        unique_together = [('race', 'stage', 'rider', 'classification')]
        indexes = [
            models.Index(fields=['race', 'stage', 'classification', 'rank']),
            models.Index(fields=['rider']),
        ]

    def __str__(self):
        return f'{self.rank}. {self.rider} ({self.classification})'


class Ranking(models.Model):
    class Kind(models.TextChoices):
        PCS = 'pcs', 'PCS'
        UCI = 'uci', 'UCI'
        TEAM = 'team', 'Équipes'

    kind = models.CharField(max_length=10, choices=Kind.choices)
    gender = models.CharField(max_length=2, default='me')  # me / we
    year = models.IntegerField()
    rider = models.ForeignKey(Rider, on_delete=models.CASCADE, null=True, blank=True, related_name='rankings')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name='rankings')
    rank = models.IntegerField()
    points = models.IntegerField(default=0)
    previous_rank = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'Classement'
        ordering = ['kind', 'rank']
        indexes = [models.Index(fields=['kind', 'year', 'rank'])]

    def __str__(self):
        who = self.rider or self.team
        return f'{self.kind} {self.year} #{self.rank} {who}'
