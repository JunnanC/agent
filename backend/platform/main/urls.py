"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("core.health.urls")),
    path("api/v2/", include("core.api.urls")),
]

handler400 = "core.response.error.bad_request_view"
handler403 = "core.response.error.permission_denied_view"
handler404 = "core.response.error.not_found_view"
handler500 = "core.response.error.server_error_view"
