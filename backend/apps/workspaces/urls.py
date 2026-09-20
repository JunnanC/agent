from django.urls import path

from apps.workspaces.views import WorkspaceSessionRouteView, WorkspaceSnapshotView

app_name = "workspaces"

urlpatterns = [
    path(
        "tasks/<str:public_id>/workspace-sessions",
        WorkspaceSessionRouteView.as_view(
            route_template="/api/v2/tasks/{public_id}/workspace-sessions",
        ),
        name="workspace-session-create",
    ),
    path(
        "workspace-sessions/<str:public_id>/renew",
        WorkspaceSessionRouteView.as_view(
            route_template="/api/v2/workspace-sessions/{public_id}/renew",
        ),
        name="workspace-session-renew",
    ),
    path(
        "workspace-sessions/<str:public_id>/revoke",
        WorkspaceSessionRouteView.as_view(
            route_template="/api/v2/workspace-sessions/{public_id}/revoke",
        ),
        name="workspace-session-revoke",
    ),
    path(
        "tasks/<str:public_id>/workspace-snapshot",
        WorkspaceSnapshotView.as_view(),
        name="workspace-snapshot",
    ),
]
