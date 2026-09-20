from django.apps import AppConfig


class AccountsAppConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "账户"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
