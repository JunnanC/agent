"""Expose the Celery app when Celery is installed.

The runtime module itself does not require Celery at import time, allowing
contract and Fake Adapter tests to run in minimal environments.
"""

from __future__ import annotations

try:
    from .celery import app as celery_app
except ImportError:  # pragma: no cover - exercised only without Celery
    celery_app = None

__all__ = ("celery_app",)
