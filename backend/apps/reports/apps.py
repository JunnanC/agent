from django.apps import AppConfig


class ReportsAppConfig(AppConfig):
    name = "apps.reports"
    label = "reports"
    verbose_name = "报告"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
