from django.apps import AppConfig


class GovernanceAppConfig(AppConfig):
    name = "apps.governance"
    label = "governance"
    verbose_name = "治理"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
