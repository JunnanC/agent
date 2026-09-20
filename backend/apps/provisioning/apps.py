from django.apps import AppConfig


class ProvisioningAppConfig(AppConfig):
    name = "apps.provisioning"
    label = "provisioning"
    verbose_name = "资源供给"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
