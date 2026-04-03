from django.db import models


class SyncLog(models.Model):
    entity_type = models.CharField(max_length=20, verbose_name='Type')
    slug = models.CharField(max_length=200, blank=True, verbose_name='Slug')
    year = models.IntegerField(null=True, blank=True, verbose_name='Année')
    success = models.BooleanField(default=True, verbose_name='Succès')
    message = models.TextField(blank=True, verbose_name='Message')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Date')

    class Meta:
        verbose_name = 'Log de synchronisation'
        verbose_name_plural = 'Logs de synchronisation'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.entity_type} {self.slug} {self.year or ''} — {'✓' if self.success else '✗'}"
