from django.apps import AppConfig


class AgentsAppConfig(AppConfig):
    name = "apps.agents"
    label = "agents"
    verbose_name = "智能体"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
