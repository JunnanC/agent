import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "education_experiment_platform.settings.local")

app = Celery("education_experiment_platform")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
