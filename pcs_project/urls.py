from django.contrib import admin
from django.urls import path, include, register_converter
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

from core.converters import PCSSlugConverter

register_converter(PCSSlugConverter, 'pcsslug')

urlpatterns = [
    # PWA : manifest + service worker servis à la racine (scope '/')
    path('manifest.webmanifest',
         TemplateView.as_view(template_name='manifest.webmanifest',
                              content_type='application/manifest+json'),
         name='manifest'),
    path('sw.js',
         TemplateView.as_view(template_name='sw.js',
                              content_type='application/javascript'),
         name='service_worker'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('api/', include('live.api_urls')),
    path('live/', include('live.urls')),
    path('', include('catalog.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
