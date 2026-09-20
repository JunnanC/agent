from django.urls import path

from apps.core.views import DownloadGrantView

app_name = "core"

urlpatterns = [
    path(
        "files/<str:asset_id>/download-grants",
        DownloadGrantView.as_view(),
        name="download-grants",
    ),
]
