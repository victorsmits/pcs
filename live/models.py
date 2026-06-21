"""Modèles temps-réel : état live d'une étape, groupes, timeline, push."""
from django.db import models

from catalog.models import Race, Stage


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
    start_time = models.CharField(max_length=10, blank=True)  # heure de départ (CET)
    finished = models.BooleanField(default=False)
    # Anti-doublon des notifications push (une seule par évènement et par session)
    notified_start = models.BooleanField(default=False)
    notified_finish = models.BooleanField(default=False)
    notified_reminder = models.BooleanField(default=False)
    last_notified_event_seq = models.IntegerField(default=0)
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


class PushSubscription(models.Model):
    """Abonnement Web Push d'un appareil (anonyme : identifié par son endpoint)."""
    endpoint = models.CharField(max_length=600, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Abonnement push'
        verbose_name_plural = 'Abonnements push'
        ordering = ['-last_seen']

    def __str__(self):
        return f'{self.endpoint[:48]}…'

    def as_dict(self):
        """Format attendu par pywebpush (subscription_info)."""
        return {'endpoint': self.endpoint,
                'keys': {'p256dh': self.p256dh, 'auth': self.auth}}


class RaceFollow(models.Model):
    """Un appareil suit une course → reçoit ses notifications push."""
    subscription = models.ForeignKey(PushSubscription, on_delete=models.CASCADE,
                                     related_name='follows')
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Suivi de course'
        verbose_name_plural = 'Suivis de course'
        unique_together = [('subscription', 'race')]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.subscription} → {self.race}'
