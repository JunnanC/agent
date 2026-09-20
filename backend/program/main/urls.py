"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("core.extend.health.urls")),
    path("api/v2/", include("core.extend.api.urls")),
]

handler400 = "core.extend.response.error.bad_request_view"
handler403 = "core.extend.response.error.permission_denied_view"
handler404 = "core.extend.response.error.not_found_view"
handler500 = "core.extend.response.error.server_error_view"
