from django.urls import path

from core.health.views import PlatformHealthView
from core.views import DownloadGrantView

app_name = "api"

urlpatterns = [
    path("platform/health", PlatformHealthView.as_view(), name="platform-health"),
    path(
        "files/<str:asset_id>/download-grants",
        DownloadGrantView.as_view(),
        name="download-grants",
    ),
]
