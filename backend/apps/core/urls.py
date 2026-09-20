from django.urls import path

from apps.core.views import DownloadGrantPlaceholderView

app_name = "core"

urlpatterns = [
    path(
        "files/<str:asset_id>/download-grants",
        DownloadGrantPlaceholderView.as_view(),
        name="download-grants",
    ),
]
