from django.urls import path

from apps.workspaces.views import (
    WorkspaceSessionCreateView,
    WorkspaceSessionRenewView,
    WorkspaceSessionRevokeView,
    WorkspaceSnapshotView,
)

app_name = "workspaces"

urlpatterns = [
    path(
        "tasks/<str:public_id>/workspace-sessions",
        WorkspaceSessionCreateView.as_view(),
        name="workspace-session-create",
    ),
    path(
        "workspace-sessions/<str:public_id>/renew",
        WorkspaceSessionRenewView.as_view(),
        name="workspace-session-renew",
    ),
    path(
        "workspace-sessions/<str:public_id>/revoke",
        WorkspaceSessionRevokeView.as_view(),
        name="workspace-session-revoke",
    ),
    path(
        "tasks/<str:public_id>/workspace-snapshot",
        WorkspaceSnapshotView.as_view(),
        name="workspace-snapshot",
    ),
]
