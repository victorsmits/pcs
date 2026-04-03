from django.db import models
from django.urls import reverse
from django.utils.text import slugify


SPECIALTY_CHOICES = [
    ('climber', 'Grimpeur'),
    ('sprinter', 'Sprinteur'),
    ('time_trialist', 'Contre-la-montre'),
    ('rouleur', 'Rouleur'),
    ('puncheur', 'Puncheur'),
    ('all_rounder', 'Polyvalent'),
    ('classics', 'Spécialiste classiques'),
    ('domestique', 'Équipier'),
]

NATIONALITY_CHOICES = [
    ('AFG', 'Afghanistan'), ('ALB', 'Albanie'), ('DZA', 'Algérie'), ('AND', 'Andorre'),
    ('ARG', 'Argentine'), ('ARM', 'Arménie'), ('AUS', 'Australie'), ('AUT', 'Autriche'),
    ('AZE', 'Azerbaïdjan'), ('BEL', 'Belgique'), ('BLR', 'Biélorussie'), ('BOL', 'Bolivie'),
    ('BRA', 'Brésil'), ('BGR', 'Bulgarie'), ('CMR', 'Cameroun'), ('CAN', 'Canada'),
    ('CHL', 'Chili'), ('CHN', 'Chine'), ('COL', 'Colombie'), ('CRI', 'Costa Rica'),
    ('HRV', 'Croatie'), ('CUB', 'Cuba'), ('CZE', 'République Tchèque'), ('DNK', 'Danemark'),
    ('ECU', 'Équateur'), ('EGY', 'Égypte'), ('ERI', 'Érythrée'), ('EST', 'Estonie'),
    ('ETH', 'Éthiopie'), ('FIN', 'Finlande'), ('FRA', 'France'), ('GBR', 'Grande-Bretagne'),
    ('GEO', 'Géorgie'), ('DEU', 'Allemagne'), ('GHA', 'Ghana'), ('GRC', 'Grèce'),
    ('GTM', 'Guatemala'), ('HUN', 'Hongrie'), ('ISL', 'Islande'), ('IND', 'Inde'),
    ('IRI', 'Iran'), ('IRL', 'Irlande'), ('ISR', 'Israël'), ('ITA', 'Italie'),
    ('JAM', 'Jamaïque'), ('JPN', 'Japon'), ('KAZ', 'Kazakhstan'), ('KEN', 'Kenya'),
    ('LAT', 'Lettonie'), ('LTU', 'Lituanie'), ('LUX', 'Luxembourg'), ('MEX', 'Mexique'),
    ('MDA', 'Moldavie'), ('MON', 'Monaco'), ('MAR', 'Maroc'), ('NLD', 'Pays-Bas'),
    ('NZL', 'Nouvelle-Zélande'), ('NOR', 'Norvège'), ('PAN', 'Panama'), ('PER', 'Pérou'),
    ('POL', 'Pologne'), ('PRT', 'Portugal'), ('ROU', 'Roumanie'), ('RUS', 'Russie'),
    ('RWA', 'Rwanda'), ('SAU', 'Arabie Saoudite'), ('SVK', 'Slovaquie'), ('SVN', 'Slovénie'),
    ('RSA', 'Afrique du Sud'), ('KOR', 'Corée du Sud'), ('ESP', 'Espagne'), ('SWE', 'Suède'),
    ('CHE', 'Suisse'), ('TPE', 'Taïwan'), ('TJK', 'Tadjikistan'), ('TUR', 'Turquie'),
    ('UKR', 'Ukraine'), ('USA', 'États-Unis'), ('URY', 'Uruguay'), ('UZB', 'Ouzbékistan'),
    ('VEN', 'Venezuela'),
]


class Rider(models.Model):
    name = models.CharField(max_length=200, verbose_name='Nom')
    slug = models.SlugField(max_length=200, unique=True, verbose_name='Slug')
    nationality = models.CharField(max_length=3, choices=NATIONALITY_CHOICES, blank=True, verbose_name='Nationalité')
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='Date de naissance')
    weight = models.FloatField(null=True, blank=True, verbose_name='Poids (kg)')
    height = models.FloatField(null=True, blank=True, verbose_name='Taille (cm)')
    specialty = models.CharField(max_length=20, choices=SPECIALTY_CHOICES, blank=True, verbose_name='Spécialité')
    photo_url = models.URLField(blank=True, verbose_name='Photo URL')
    current_team = models.ForeignKey(
        'teams.Team', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='current_riders', verbose_name='Équipe actuelle'
    )
    pcs_url = models.URLField(blank=True, verbose_name='URL PCS')
    uci_id = models.CharField(max_length=100, blank=True, verbose_name='ID UCI')
    is_active = models.BooleanField(default=True, verbose_name='Actif')
    pcs_points = models.IntegerField(default=0, verbose_name='Points PCS')
    pcs_rank = models.IntegerField(null=True, blank=True, verbose_name='Classement PCS')
    uci_points = models.FloatField(default=0, verbose_name='Points UCI')
    uci_rank = models.IntegerField(null=True, blank=True, verbose_name='Classement UCI')
    one_day_wins = models.IntegerField(default=0, verbose_name='Victoires 1 jour')
    stage_wins = models.IntegerField(default=0, verbose_name='Victoires d\'étapes')
    gc_wins = models.IntegerField(default=0, verbose_name='Victoires GC')
    grand_tour_wins = models.IntegerField(default=0, verbose_name='Grands Tours gagnés')
    monument_wins = models.IntegerField(default=0, verbose_name='Monuments gagnés')
    profile_score = models.IntegerField(default=0, verbose_name='Score profil')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Coureur'
        verbose_name_plural = 'Coureurs'
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['nationality']),
            models.Index(fields=['pcs_rank']),
            models.Index(fields=['specialty']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('riders:rider_detail', kwargs={'slug': self.slug})

    @property
    def age(self):
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None

    @property
    def flag_code(self):
        mapping = {
            'FRA': 'fr', 'BEL': 'be', 'ITA': 'it', 'ESP': 'es', 'GBR': 'gb',
            'DEU': 'de', 'NLD': 'nl', 'SVN': 'si', 'COL': 'co', 'AUS': 'au',
            'DNK': 'dk', 'NOR': 'no', 'SWE': 'se', 'CHE': 'ch', 'USA': 'us',
            'CAN': 'ca', 'PRT': 'pt', 'KAZ': 'kz', 'POL': 'pl', 'RUS': 'ru',
            'UKR': 'ua', 'LTU': 'lt', 'LAT': 'lv', 'EST': 'ee', 'AUT': 'at',
            'SVK': 'sk', 'HRV': 'hr', 'ROU': 'ro', 'HUN': 'hu', 'CZE': 'cz',
            'NZL': 'nz', 'RWA': 'rw', 'ERI': 'er', 'ETH': 'et', 'RSA': 'za',
            'ARG': 'ar', 'BRA': 'br', 'MEX': 'mx', 'URY': 'uy', 'CHL': 'cl',
            'ECU': 'ec', 'GEO': 'ge', 'ARM': 'am', 'AZE': 'az', 'UZB': 'uz',
        }
        return mapping.get(self.nationality, 'xx')


class RiderSeasonStats(models.Model):
    rider = models.ForeignKey(Rider, on_delete=models.CASCADE, related_name='season_stats', verbose_name='Coureur')
    year = models.IntegerField(verbose_name='Année')
    team = models.ForeignKey(
        'teams.Team', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rider_season_stats', verbose_name='Équipe'
    )
    points = models.FloatField(default=0, verbose_name='Points')
    rank = models.IntegerField(null=True, blank=True, verbose_name='Classement')
    wins = models.IntegerField(default=0, verbose_name='Victoires')
    podiums = models.IntegerField(default=0, verbose_name='Podiums')
    top10 = models.IntegerField(default=0, verbose_name='Top 10')
    races_ridden = models.IntegerField(default=0, verbose_name='Courses disputées')
    days_in_race = models.IntegerField(default=0, verbose_name='Jours de course')
    distance_raced = models.FloatField(default=0, verbose_name='Distance parcourue (km)')

    class Meta:
        verbose_name = 'Statistiques saisonnières'
        verbose_name_plural = 'Statistiques saisonnières'
        unique_together = [('rider', 'year')]
        ordering = ['-year']

    def __str__(self):
        return f"{self.rider.name} - {self.year}"


class RaceResult(models.Model):
    rider = models.ForeignKey(Rider, on_delete=models.CASCADE, related_name='race_results', verbose_name='Coureur')
    race = models.ForeignKey('races.Race', on_delete=models.CASCADE, related_name='race_results', verbose_name='Course')
    stage = models.ForeignKey(
        'races.Stage', on_delete=models.CASCADE, null=True, blank=True,
        related_name='stage_results', verbose_name='Étape'
    )
    team = models.ForeignKey(
        'teams.Team', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='team_results', verbose_name='Équipe'
    )
    year = models.IntegerField(verbose_name='Année')
    rank = models.IntegerField(null=True, blank=True, verbose_name='Position')
    time = models.DurationField(null=True, blank=True, verbose_name='Temps')
    time_gap = models.CharField(max_length=20, blank=True, verbose_name='Écart')
    points = models.FloatField(default=0, verbose_name='Points')
    uci_points = models.FloatField(default=0, verbose_name='Points UCI')
    dnf = models.BooleanField(default=False, verbose_name='Abandon')
    dns = models.BooleanField(default=False, verbose_name='Non partant')
    dsq = models.BooleanField(default=False, verbose_name='Disqualifié')
    is_stage = models.BooleanField(default=False, verbose_name='Résultat d\'étape')
    result_type = models.CharField(
        max_length=20, default='gc',
        choices=[
            ('gc', 'Classement Général'),
            ('stage', 'Étape'),
            ('points', 'Points'),
            ('kom', 'Montagne'),
            ('youth', 'Jeunes'),
            ('team', 'Équipes'),
        ],
        verbose_name='Type de résultat'
    )

    class Meta:
        verbose_name = 'Résultat'
        verbose_name_plural = 'Résultats'
        ordering = ['rank']
        indexes = [
            models.Index(fields=['rider', 'year']),
            models.Index(fields=['race', 'stage']),
            models.Index(fields=['rank']),
        ]

    def __str__(self):
        return f"{self.rider.name} - {self.race.name} {self.year} - #{self.rank}"

    @property
    def status(self):
        if self.dnf:
            return 'DNF'
        if self.dns:
            return 'DNS'
        if self.dsq:
            return 'DSQ'
        return str(self.rank) if self.rank else '-'
