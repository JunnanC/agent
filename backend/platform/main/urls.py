"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

from core.views import LiveHealthView, ReadyHealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/live", LiveHealthView.as_view(), name="health-live"),
    path("health/ready", ReadyHealthView.as_view(), name="health-ready"),
    path("api/v2/", include("core.urls")),
]

handler400 = "core.exceptions.bad_request_view"
handler403 = "core.exceptions.permission_denied_view"
handler404 = "core.exceptions.not_found_view"
handler500 = "core.exceptions.server_error_view"
