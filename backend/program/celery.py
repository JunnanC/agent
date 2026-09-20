"""Celery application for the modular Django monolith and independent worker."""

from __future__ import annotations

import os

try:
    from celery import Celery
except ImportError:  # pragma: no cover - minimal contract environments omit Celery
    app = None
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

    app = Celery("main")
    app.config_from_object("django.conf:settings", namespace="CELERY")
    app.autodiscover_tasks()
