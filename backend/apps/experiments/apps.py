from django.apps import AppConfig


class ExperimentsAppConfig(AppConfig):
    name = "apps.experiments"
    label = "experiments"
    verbose_name = "实验"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
