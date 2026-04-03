from django.contrib import admin
from django.contrib.admin import AdminSite
from django.urls import path
from django.shortcuts import render
from django.http import JsonResponse
from django.core.cache import cache

admin.site.site_header = 'CycloStats Administration'
admin.site.site_title = 'CycloStats Admin'
admin.site.index_title = 'Tableau de bord'


def _admin_sync_view(request):
    """Admin-embedded sync page using admin base template."""
    from core.views import SYNC_TYPES, _run_sync
    import threading, uuid
    from datetime import date

    if request.method == 'POST':
        sync_type = request.POST.get('sync_type', 'races')
        years_raw = request.POST.getlist('years')
        years = [int(y) for y in years_raw if y.isdigit()]
        if not years:
            years = [date.today().year]
        job_id = uuid.uuid4().hex
        cache.set(f'sync:{job_id}:log',  [], timeout=7200)
        cache.set(f'sync:{job_id}:done', False, timeout=7200)
        threading.Thread(target=_run_sync, args=(job_id, sync_type, years), daemon=True).start()
        return JsonResponse({'job_id': job_id})

    years_available = list(range(date.today().year + 1, 2019, -1))
    context = {
        **admin.site.each_context(request),
        'title': 'Synchronisation PCS',
        'years_available': years_available,
        'default_years': [str(date.today().year)],
        'sync_types': SYNC_TYPES,
    }
    return render(request, 'admin/sync.html', context)


def _admin_sync_status(request, job_id):
    """Status polling endpoint (reuse core view)."""
    from core.views import sync_status_api
    return sync_status_api(request, job_id)


# Patch AdminSite.get_urls to inject /admin/sync/
_orig_get_urls = AdminSite.get_urls


def _custom_get_urls(self):
    custom = [
        path('sync/', self.admin_view(_admin_sync_view), name='admin_sync'),
        path('sync/<str:job_id>/status/', self.admin_view(_admin_sync_status), name='admin_sync_status'),
    ]
    return custom + _orig_get_urls(self)


AdminSite.get_urls = _custom_get_urls
