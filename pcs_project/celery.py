"""Celery application for PCS Live."""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pcs_project.settings')

app = Celery('pcs_live')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
