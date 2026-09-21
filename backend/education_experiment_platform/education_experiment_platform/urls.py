from django.urls import include, path, re_path

from .api import api_not_found
from .metrics import metrics

urlpatterns = [
    path("api/v2/", include("education_experiment_platform.api_urls")),
    path("internal/metrics", metrics, name="metrics"),
    re_path(r"^api/v2/(?P<_path>.*)$", api_not_found, name="api-not-found"),
]
