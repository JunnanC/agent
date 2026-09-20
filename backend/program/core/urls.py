"""Top-level routes outside the /api/v2 partition."""

from django.urls import path

from core.views import FileDownloadView

app_name = "core"

urlpatterns = [
    path(
        "files/<str:one_time_token>",
        FileDownloadView.as_view(),
        name="file-download",
    ),
]
