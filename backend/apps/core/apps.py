from django.apps import AppConfig


class CoreAppConfig(AppConfig):
    name = "apps.core"
    label = "core"
    verbose_name = "公共核心"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
