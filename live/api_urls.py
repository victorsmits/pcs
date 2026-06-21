from django.urls import path

from live import api

app_name = 'live_api'

urlpatterns = [
    path('live/today/', api.today_live, name='today'),
    path('race/<pcsslug:slug>/<int:year>/stage/<int:number>/live/', api.stage_live_data, name='stage_live_data'),
]
