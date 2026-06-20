from django.db import models


class SyncLog(models.Model):
    """Trace d'une opération de synchronisation PCS (supervision dans l'admin)."""

    class Status(models.TextChoices):
        OK = 'ok', 'Succès'
        ERROR = 'error', 'Erreur'
        EMPTY = 'empty', 'Vide'

    entity_type = models.CharField(max_length=40, verbose_name='Type')   # calendar, race, stage, rider, team, live
    ref = models.CharField(max_length=200, blank=True, verbose_name='Référence')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OK)
    message = models.TextField(blank=True)
    duration_ms = models.IntegerField(null=True, blank=True, verbose_name='Durée (ms)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log de synchronisation'
        verbose_name_plural = 'Logs de synchronisation'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['entity_type', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'[{self.status}] {self.entity_type} {self.ref} ({self.created_at:%Y-%m-%d %H:%M})'
