from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.common.health import health
from apps.common.probes.views import PlatformHealthView

urlpatterns = [
    path("health/", include("apps.common.probes.urls")),
    path("api/v1/platform/health", PlatformHealthView.as_view(), name="platform-health"),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("admin/health", health),
    path("admin/", include("apps.common.urls")),
    path("api/v1/", include("apps.membership.urls")),
    path("", include("apps.identity.urls")),
]
