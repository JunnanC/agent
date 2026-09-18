from django.urls import include, path

from apps.common.health import health

urlpatterns = [
    path("admin/health", health),
    path("admin/", include("apps.common.urls")),
    path("api/v1/", include("apps.membership.urls")),
    path("", include("apps.identity.urls")),
]
