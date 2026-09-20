from django.urls import path

from core.health.views import PlatformHealthView

app_name = "api"

urlpatterns = [
    path("platform/health", PlatformHealthView.as_view(), name="platform-health"),
]
