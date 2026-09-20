from django.apps import AppConfig


class WorkspacesAppConfig(AppConfig):
    name = "apps.workspaces"
    label = "workspaces"
    verbose_name = "工作区"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
