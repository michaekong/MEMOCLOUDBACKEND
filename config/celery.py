import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

# Charger config depuis settings.py
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover des tasks.py dans toutes les apps
app.autodiscover_tasks()
