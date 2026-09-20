from django.urls import include, path

from apps.core.views import FileDownloadPlaceholderView, HealthView

urlpatterns = [
    path(
        "files/<str:one_time_token>",
        FileDownloadPlaceholderView.as_view(),
        name="file-download",
    ),
    path("health", HealthView.as_view(), name="health"),
    path("internal/workspace-tokens/", include("apps.workspaces.internal_urls")),
    path("api/v2/", include("education_experiment_platform.api_urls")),
]

handler400 = "apps.core.middleware.bad_request"
handler404 = "apps.core.middleware.not_found"
handler405 = "apps.core.middleware.method_not_allowed"
