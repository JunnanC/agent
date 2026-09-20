from django.apps import AppConfig


class NotificationsAppConfig(AppConfig):
    name = "apps.notifications"
    label = "notifications"
    verbose_name = "通知"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
