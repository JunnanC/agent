from django.urls import path
from drf_spectacular.views import SpectacularAPIView

from .events import EventStreamView
from .health import HealthView, ReadinessView

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("health/ready", ReadinessView.as_view(), name="readiness"),
    path("events/stream", EventStreamView.as_view(), name="event-stream"),
    path("schema", SpectacularAPIView.as_view(), name="openapi-schema"),
]
