"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("core.health.urls")),
    path("api/v2/", include("core.urls")),
]

handler400 = "core.exceptions.bad_request_view"
handler403 = "core.exceptions.permission_denied_view"
handler404 = "core.exceptions.not_found_view"
handler500 = "core.exceptions.server_error_view"
