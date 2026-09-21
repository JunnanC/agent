from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from .events import EventStreamView
from .health import HealthView, ReadinessView

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("health/ready", ReadinessView.as_view(), name="readiness"),
    path("events/stream", EventStreamView.as_view(), name="event-stream"),
    path("schema", SpectacularAPIView.as_view(), name="openapi-schema"),
    # 教师端（doc 02 §7.1 路由视角：/api/v2/teaching/*）。
    # 前缀只在这里出现一次，app 内部只声明相对段。
    path("teaching/", include("apps.courses.urls")),
]
