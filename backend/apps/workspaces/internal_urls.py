from django.urls import path

from apps.workspaces.views import WorkspaceTokenVerifyView

app_name = "workspaces-internal"

urlpatterns = [
    path(
        "verify",
        WorkspaceTokenVerifyView.as_view(),
        name="workspace-token-verify",
    ),
]
