from django.apps import AppConfig


class LabtemplatesAppConfig(AppConfig):
    name = "apps.labtemplates"
    label = "labtemplates"
    verbose_name = "实验模板"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
