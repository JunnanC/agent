from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.views import PlatformHealthView

app_name = "core"

urlpatterns = [
    path("platform/health", PlatformHealthView.as_view(), name="platform-health"),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path(
        "docs",
        SpectacularSwaggerView.as_view(url_name="core:schema"),
        name="docs",
    ),
]
