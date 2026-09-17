from django.urls import path

from apps.common.health import health

urlpatterns = [
    path("admin/health", health),
]
