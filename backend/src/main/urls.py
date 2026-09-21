"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

from common.health.views import PlatformHealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("common.health.urls")),
    path(
        "api/v2/",
        include(
            (
                [path("platform/health", PlatformHealthView.as_view(), name="platform-health")],
                "api",
            ),
            namespace="api",
        ),
    ),
]

handler400 = "common.response.error.bad_request_view"
handler403 = "common.response.error.permission_denied_view"
handler404 = "common.response.error.not_found_view"
handler500 = "common.response.error.server_error_view"
