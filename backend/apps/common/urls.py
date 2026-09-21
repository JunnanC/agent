from django.urls import path

from . import views

urlpatterns = [
    path("audit-logs", views.audit_logs),
    path("audit-logs/export", views.export_audit_logs),
    path("audit-logs/export/<str:operation_id>", views.audit_export_status),
]
