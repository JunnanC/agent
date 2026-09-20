from django.apps import AppConfig


class ArchivesAppConfig(AppConfig):
    name = "apps.archives"
    label = "archives"
    verbose_name = "归档"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
