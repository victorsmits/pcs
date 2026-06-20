"""Modèles temps-réel : état live d'une étape, groupes, timeline."""
from django.db import models

from catalog.models import Stage


class LiveSession(models.Model):
    """État live d'une étape suivie. Un enregistrement par étape."""

    class Status(models.TextChoices):
        PREVIEW = 'preview', 'Avant course'
        RACING = 'racing', 'En course'
        FINISHED = 'finished', 'Terminée'
        UNKNOWN = 'unknown', 'Inconnu'

    stage = models.OneToOneField(Stage, on_delete=models.CASCADE, related_name='live_session')
    pcs_live_id = models.IntegerField(null=True, blank=True)  # data.ls_pid
    race_status = models.CharField(max_length=12, choices=Status.choices, default=Status.UNKNOWN)
    km_done = models.FloatField(null=True, blank=True)
    km_to_go = models.FloatField(null=True, blank=True)
    max_km = models.FloatField(null=True, blank=True)
    perc = models.FloatField(null=True, blank=True)         # progression %
    avg_speed = models.FloatField(null=True, blank=True)
    min_ele = models.IntegerField(null=True, blank=True)
    max_ele = models.IntegerField(null=True, blank=True)
    started_ts = models.BigIntegerField(null=True, blank=True)
    finished = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True,
                                    help_text='Si vrai, le worker poll cette session.')
    raw_data = models.JSONField(default=dict, blank=True)   # dernier objet `data` brut
    last_polled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Session live'
        verbose_name_plural = 'Sessions live'
        ordering = ['-updated_at']

    def __str__(self):
        return f'Live {self.stage} [{self.race_status}]'


class LiveGroup(models.Model):
    """Un groupe de course (peloton, échappée, chasse…) à un instant donné."""
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='groups')
    order = models.IntegerField(default=0)
    label = models.CharField(max_length=80)        # P=Peloton, échappée…
    gap = models.CharField(max_length=20, blank=True)
    rider_count = models.IntegerField(null=True, blank=True)
    riders = models.JSONField(default=list, blank=True)
    km_point = models.FloatField(null=True, blank=True)
    profile_pct = models.FloatField(null=True, blank=True)  # position horizontale sur le profil

    class Meta:
        verbose_name = 'Groupe live'
        ordering = ['order']

    def __str__(self):
        return f'{self.label} (+{self.gap})'


class LiveEvent(models.Model):
    """Événement de la timeline live (HTML pré-rendu par PCS ou texte)."""
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='events')
    seqnr = models.IntegerField(null=True, blank=True, db_index=True)
    marker = models.CharField(max_length=40, blank=True)  # km / P / F …
    text = models.TextField(blank=True)
    html = models.TextField(blank=True)
    kind = models.CharField(max_length=20, blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Événement live'
        ordering = ['-order', '-seqnr']
        unique_together = [('session', 'seqnr')]

    def __str__(self):
        return f'{self.marker} {self.text[:40]}'
