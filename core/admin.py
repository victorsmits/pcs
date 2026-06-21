import json

from django.contrib import admin
from django.utils.module_loading import import_string

from core.models import SyncLog


# --- Tâches périodiques : ajout d'une action « Exécuter maintenant » ---
try:
    from django_celery_beat.models import PeriodicTask
    from django_celery_beat.admin import PeriodicTaskAdmin

    admin.site.unregister(PeriodicTask)

    @admin.register(PeriodicTask)
    class RunnablePeriodicTaskAdmin(PeriodicTaskAdmin):
        @admin.action(description='Exécuter maintenant (synchrone)')
        def run_now(self, request, queryset):
            for pt in queryset:
                try:
                    task = import_string(pt.task)
                    args = json.loads(pt.args or '[]')
                    kwargs = json.loads(pt.kwargs or '{}')
                    result = task.apply(args=args, kwargs=kwargs)
                    self.message_user(request, f'« {pt.name} » exécutée → {result.result}')
                except Exception as exc:  # noqa: BLE001
                    self.message_user(request, f'« {pt.name} » : erreur {exc}',
                                      level='error')

        def get_actions(self, request):
            actions = super().get_actions(request)
            actions['run_now'] = self.get_action('run_now')
            return actions
except Exception:  # noqa: BLE001 — django_celery_beat absent
    pass


# --- Désencombrement : on retire de l'admin les modèles tiers inutiles ici ---
def _unregister(label, model):
    try:
        from django.apps import apps
        admin.site.unregister(apps.get_model(label, model))
    except Exception:  # noqa: BLE001
        pass


for _lbl, _mdl in [
    ('sites', 'Site'),
    ('socialaccount', 'SocialApp'),      # identifiants via variables d'env, pas la BDD
    ('socialaccount', 'SocialToken'),
    ('django_celery_beat', 'ClockedSchedule'),
    ('django_celery_beat', 'SolarSchedule'),
    ('django_celery_results', 'GroupResult'),
]:
    _unregister(_lbl, _mdl)


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'entity_type', 'ref', 'status', 'duration_ms')
    list_filter = ('status', 'entity_type', 'created_at')
    search_fields = ('ref', 'message')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    change_list_template = 'admin/synclog_changelist.html'

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [path('clear-cache/', self.admin_site.admin_view(self.clear_cache_view),
                       name='core_synclog_clear_cache')]
        return custom + urls

    def clear_cache_view(self, request):
        from django.core.cache import cache
        from django.contrib import messages
        from django.shortcuts import redirect
        cache.clear()
        messages.success(request, 'Cache PCS vidé. Les prochaines pages seront resynchronisées depuis PCS.')
        return redirect('admin:core_synclog_changelist')
