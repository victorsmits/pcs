from django.db import models


RANKING_TYPE_CHOICES = [
    ('pcs', 'PCS Points'),
    ('uci', 'UCI Points'),
    ('uci_team', 'UCI Équipes'),
    ('wins', 'Victoires'),
]


class RiderRanking(models.Model):
    rider = models.ForeignKey(
        'riders.Rider', on_delete=models.CASCADE, related_name='rankings', verbose_name='Coureur'
    )
    ranking_type = models.CharField(max_length=20, choices=RANKING_TYPE_CHOICES, default='pcs', verbose_name='Type')
    year = models.IntegerField(verbose_name='Année')
    rank = models.IntegerField(verbose_name='Position')
    points = models.FloatField(default=0, verbose_name='Points')
    previous_rank = models.IntegerField(null=True, blank=True, verbose_name='Position précédente')
    team = models.ForeignKey(
        'teams.Team', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rider_rankings', verbose_name='Équipe'
    )
    nationality = models.CharField(max_length=3, blank=True, verbose_name='Nationalité')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Classement coureur'
        verbose_name_plural = 'Classements coureurs'
        ordering = ['rank']
        unique_together = [('rider', 'ranking_type', 'year')]
        indexes = [
            models.Index(fields=['ranking_type', 'year', 'rank']),
            models.Index(fields=['year']),
        ]

    def __str__(self):
        return f"#{self.rank} {self.rider.name} ({self.year} - {self.ranking_type})"

    @property
    def rank_change(self):
        if self.previous_rank is None:
            return None
        return self.previous_rank - self.rank


class TeamRanking(models.Model):
    team = models.ForeignKey(
        'teams.Team', on_delete=models.CASCADE, related_name='rankings', verbose_name='Équipe'
    )
    ranking_type = models.CharField(max_length=20, choices=RANKING_TYPE_CHOICES, default='uci_team', verbose_name='Type')
    year = models.IntegerField(verbose_name='Année')
    rank = models.IntegerField(verbose_name='Position')
    points = models.FloatField(default=0, verbose_name='Points')
    previous_rank = models.IntegerField(null=True, blank=True, verbose_name='Position précédente')
    wins = models.IntegerField(default=0, verbose_name='Victoires')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Classement équipe'
        verbose_name_plural = 'Classements équipes'
        ordering = ['rank']
        unique_together = [('team', 'ranking_type', 'year')]
        indexes = [
            models.Index(fields=['ranking_type', 'year', 'rank']),
        ]

    def __str__(self):
        return f"#{self.rank} {self.team.name} ({self.year} - {self.ranking_type})"

    @property
    def rank_change(self):
        if self.previous_rank is None:
            return None
        return self.previous_rank - self.rank
