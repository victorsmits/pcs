from django.urls import path

from live import api

app_name = 'live_api'

urlpatterns = [
    path('live/today/', api.today_live, name='today'),
    path('race/<pcsslug:slug>/<int:year>/stage/<int:number>/live/', api.stage_live_data, name='stage_live_data'),
    # Notifications push
    path('push/config/', api.push_config, name='push_config'),
    path('push/subscribe/', api.push_subscribe, name='push_subscribe'),
    path('push/follow/', api.push_follow, name='push_follow'),
    path('push/following/', api.push_following, name='push_following'),
]
