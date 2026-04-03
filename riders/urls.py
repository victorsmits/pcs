from django.urls import path
from riders import views

app_name = 'riders'

urlpatterns = [
    path('', views.rider_list, name='rider_list'),
    path('compare/', views.rider_compare, name='rider_compare'),
    path('<slug:slug>/', views.rider_detail, name='rider_detail'),
    path('<slug:slug>/fetch/', views.rider_fetch, name='rider_fetch'),
    path('<slug:slug>/stats/', views.rider_stats_api, name='rider_stats_api'),
]
