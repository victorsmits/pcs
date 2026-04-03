from django.db import models
from django.urls import reverse
from django.utils.text import slugify


TEAM_STATUS_CHOICES = [
    ('WorldTeam', 'UCI WorldTeam'),
    ('ProTeam', 'UCI ProTeam'),
    ('Continental', 'Continental'),
    ('Women', 'Women\'s Team'),
    ('National', 'Équipe Nationale'),
]


class Team(models.Model):
    name = models.CharField(max_length=200, verbose_name='Nom')
    slug = models.SlugField(max_length=200, verbose_name='Slug')
    year = models.IntegerField(verbose_name='Année')
    nationality = models.CharField(max_length=3, blank=True, verbose_name='Nationalité')
    country_name = models.CharField(max_length=100, blank=True, verbose_name='Pays')
    status = models.CharField(
        max_length=20, choices=TEAM_STATUS_CHOICES, default='Continental', verbose_name='Statut'
    )
    abbreviation = models.CharField(max_length=10, blank=True, verbose_name='Abréviation')
    jersey_url = models.URLField(blank=True, verbose_name='URL maillot')
    logo_url = models.URLField(blank=True, verbose_name='URL logo')
    bike_brand = models.CharField(max_length=100, blank=True, verbose_name='Vélo')
    clothing_brand = models.CharField(max_length=100, blank=True, verbose_name='Équipementier')
    manager = models.CharField(max_length=200, blank=True, verbose_name='Directeur sportif')
    website = models.URLField(blank=True, verbose_name='Site web')
    pcs_url = models.URLField(blank=True, verbose_name='URL PCS')
    wins = models.IntegerField(default=0, verbose_name='Victoires')
    points = models.FloatField(default=0, verbose_name='Points')
    team_rank = models.IntegerField(null=True, blank=True, verbose_name='Classement')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Équipe'
        verbose_name_plural = 'Équipes'
        ordering = ['name']
        unique_together = [('slug', 'year')]
        indexes = [
            models.Index(fields=['slug', 'year']),
            models.Index(fields=['year']),
            models.Index(fields=['status']),
            models.Index(fields=['nationality']),
        ]

    def __str__(self):
        return f"{self.name} ({self.year})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('teams:team_detail', kwargs={'slug': self.slug, 'year': self.year})

    @property
    def flag_code(self):
        mapping = {
            'FRA': 'fr', 'BEL': 'be', 'ITA': 'it', 'ESP': 'es', 'GBR': 'gb',
            'DEU': 'de', 'NLD': 'nl', 'AUS': 'au', 'USA': 'us', 'CHE': 'ch',
            'DNK': 'dk', 'NOR': 'no', 'SWE': 'se', 'COL': 'co', 'SVN': 'si',
            'POL': 'pl', 'PRT': 'pt', 'KAZ': 'kz', 'LTU': 'lt', 'LAT': 'lv',
        }
        return mapping.get(self.nationality, 'xx')


class TeamRoster(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='roster', verbose_name='Équipe')
    rider = models.ForeignKey(
        'riders.Rider', on_delete=models.CASCADE, related_name='team_history', verbose_name='Coureur'
    )
    role = models.CharField(
        max_length=20, default='rider',
        choices=[
            ('rider', 'Coureur'),
            ('captain', 'Capitaine de route'),
            ('domestique', 'Équipier'),
        ],
        verbose_name='Rôle'
    )
    joined_date = models.DateField(null=True, blank=True, verbose_name='Date d\'arrivée')
    left_date = models.DateField(null=True, blank=True, verbose_name='Date de départ')

    class Meta:
        verbose_name = 'Effectif'
        verbose_name_plural = 'Effectifs'
        unique_together = [('team', 'rider')]

    def __str__(self):
        return f"{self.rider.name} - {self.team.name} {self.team.year}"
