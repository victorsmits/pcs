from django.db import models
from django.urls import reverse
from django.utils.text import slugify


CLASSIFICATION_CHOICES = [
    ('1.UWT', '1.UWT - WorldTour 1 jour'),
    ('2.UWT', '2.UWT - WorldTour Étapes'),
    ('1.Pro', '1.Pro - ProSeries 1 jour'),
    ('2.Pro', '2.Pro - ProSeries Étapes'),
    ('1.1', '1.1 - Elite 1 jour'),
    ('2.1', '2.1 - Elite Étapes'),
    ('1.2', '1.2 - Nationale/Continentale 1 jour'),
    ('2.2', '2.2 - Nationale/Continentale Étapes'),
    ('CC', 'CC - Championnat Continental'),
    ('CN', 'CN - Championnat National'),
    ('WC', 'WC - Championnat du Monde'),
    ('OG', 'OG - Jeux Olympiques'),
    ('1.WWT', '1.WWT - Women WorldTour 1 jour'),
    ('2.WWT', '2.WWT - Women WorldTour Étapes'),
]

CIRCUIT_CHOICES = [
    ('UCI World Tour', 'UCI World Tour'),
    ('UCI ProSeries', 'UCI ProSeries'),
    ('UCI Continental Circuit', 'UCI Continental Circuit'),
    ('UCI Europe Tour', 'UCI Europe Tour'),
    ('UCI America Tour', 'UCI America Tour'),
    ('UCI Asia Tour', 'UCI Asia Tour'),
    ('UCI Africa Tour', 'UCI Africa Tour'),
    ('UCI Oceania Tour', 'UCI Oceania Tour'),
    ('UCI Women WorldTour', 'UCI Women WorldTour'),
    ('National Championships', 'Championnats Nationaux'),
    ('World Championships', 'Championnats du Monde'),
    ('Olympic Games', 'Jeux Olympiques'),
]

STAGE_TYPE_CHOICES = [
    ('flat', 'Plat'),
    ('hilly', 'Vallonné'),
    ('mountain', 'Montagne'),
    ('mountain_finish', 'Arrivée en altitude'),
    ('tt', 'Contre-la-montre'),
    ('itt', 'Contre-la-montre individuel'),
    ('ttt', 'Contre-la-montre par équipes'),
    ('cobbles', 'Pavés'),
    ('prologue', 'Prologue'),
]


class Race(models.Model):
    name = models.CharField(max_length=200, verbose_name='Nom')
    slug = models.SlugField(max_length=200, verbose_name='Slug')
    year = models.IntegerField(verbose_name='Année')
    classification = models.CharField(
        max_length=10, choices=CLASSIFICATION_CHOICES, blank=True, verbose_name='Classification'
    )
    circuit = models.CharField(max_length=50, choices=CIRCUIT_CHOICES, blank=True, verbose_name='Circuit')
    country = models.CharField(max_length=3, blank=True, verbose_name='Pays')
    country_name = models.CharField(max_length=100, blank=True, verbose_name='Pays (nom)')
    start_date = models.DateField(null=True, blank=True, verbose_name='Date de départ')
    end_date = models.DateField(null=True, blank=True, verbose_name='Date de fin')
    distance = models.FloatField(null=True, blank=True, verbose_name='Distance (km)')
    stages_count = models.IntegerField(default=1, verbose_name='Nombre d\'étapes')
    is_stage_race = models.BooleanField(default=False, verbose_name='Course par étapes')
    is_monument = models.BooleanField(default=False, verbose_name='Monument')
    is_grand_tour = models.BooleanField(default=False, verbose_name='Grand Tour')
    edition = models.IntegerField(null=True, blank=True, verbose_name='Édition')
    departure_city = models.CharField(max_length=100, blank=True, verbose_name='Ville de départ')
    arrival_city = models.CharField(max_length=100, blank=True, verbose_name='Ville d\'arrivée')
    winner = models.ForeignKey(
        'riders.Rider', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='won_races', verbose_name='Vainqueur'
    )
    winner_team = models.ForeignKey(
        'teams.Team', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='won_races', verbose_name='Équipe vainqueur'
    )
    pcs_url = models.URLField(blank=True, verbose_name='URL PCS')
    photo_url = models.URLField(blank=True, verbose_name='Photo URL')
    description = models.TextField(blank=True, verbose_name='Description')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Course'
        verbose_name_plural = 'Courses'
        ordering = ['-start_date']
        unique_together = [('slug', 'year')]
        indexes = [
            models.Index(fields=['slug', 'year']),
            models.Index(fields=['year']),
            models.Index(fields=['classification']),
            models.Index(fields=['start_date']),
            models.Index(fields=['is_grand_tour']),
            models.Index(fields=['is_monument']),
        ]

    def __str__(self):
        return f"{self.name} {self.year}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('races:race_detail', kwargs={'slug': self.slug, 'year': self.year})

    @property
    def duration_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return None

    @property
    def flag_code(self):
        mapping = {
            'FRA': 'fr', 'BEL': 'be', 'ITA': 'it', 'ESP': 'es', 'GBR': 'gb',
            'DEU': 'de', 'NLD': 'nl', 'SVN': 'si', 'COL': 'co', 'AUS': 'au',
            'DNK': 'dk', 'NOR': 'no', 'SWE': 'se', 'CHE': 'ch', 'USA': 'us',
            'POL': 'pl', 'PRT': 'pt', 'MLT': 'mt', 'CAN': 'ca',
        }
        return mapping.get(self.country, 'xx')


class Stage(models.Model):
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='stages', verbose_name='Course')
    number = models.IntegerField(verbose_name='Numéro')
    name = models.CharField(max_length=200, blank=True, verbose_name='Nom')
    date = models.DateField(null=True, blank=True, verbose_name='Date')
    departure = models.CharField(max_length=100, blank=True, verbose_name='Départ')
    arrival = models.CharField(max_length=100, blank=True, verbose_name='Arrivée')
    distance = models.FloatField(null=True, blank=True, verbose_name='Distance (km)')
    stage_type = models.CharField(
        max_length=20, choices=STAGE_TYPE_CHOICES, default='flat', verbose_name='Type d\'étape'
    )
    elevation_gain = models.IntegerField(null=True, blank=True, verbose_name='Dénivelé positif (m)')
    winner = models.ForeignKey(
        'riders.Rider', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stage_wins_rel', verbose_name='Vainqueur'
    )
    winner_team = models.ForeignKey(
        'teams.Team', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stage_wins_rel', verbose_name='Équipe vainqueur'
    )
    leader_after = models.ForeignKey(
        'riders.Rider', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stages_led', verbose_name='Leader après l\'étape'
    )
    pcs_url = models.URLField(blank=True, verbose_name='URL PCS')
    profile_url = models.URLField(blank=True, verbose_name='URL profil')

    class Meta:
        verbose_name = 'Étape'
        verbose_name_plural = 'Étapes'
        ordering = ['number']
        unique_together = [('race', 'number')]
        indexes = [
            models.Index(fields=['race', 'number']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.race.name} {self.race.year} - Étape {self.number}"

    def get_absolute_url(self):
        return reverse('races:stage_detail', kwargs={
            'slug': self.race.slug, 'year': self.race.year, 'stage_num': self.number
        })

    @property
    def type_icon(self):
        icons = {
            'flat': '🟢',
            'hilly': '🟡',
            'mountain': '🔴',
            'mountain_finish': '🔴',
            'tt': '⏱️',
            'itt': '⏱️',
            'ttt': '⏱️',
            'cobbles': '⬛',
            'prologue': '⏱️',
        }
        return icons.get(self.stage_type, '⚪')


class StartList(models.Model):
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='start_list', verbose_name='Course')
    rider = models.ForeignKey(
        'riders.Rider', on_delete=models.CASCADE, related_name='start_lists', verbose_name='Coureur'
    )
    team = models.ForeignKey(
        'teams.Team', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='start_lists', verbose_name='Équipe'
    )
    bib_number = models.IntegerField(null=True, blank=True, verbose_name='Dossard')
    withdrew = models.BooleanField(default=False, verbose_name='Forfait')

    class Meta:
        verbose_name = 'Liste de départ'
        verbose_name_plural = 'Listes de départ'
        unique_together = [('race', 'rider')]

    def __str__(self):
        return f"{self.race} - {self.rider.name}"
