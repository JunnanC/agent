from django.urls import include, path


urlpatterns = [
    path("", include("apps.notifications.urls")),
    path("", include("apps.core.urls")),
    path("", include("apps.workspaces.urls")),
]
