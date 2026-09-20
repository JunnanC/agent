from django.apps import AppConfig


class ReviewsAppConfig(AppConfig):
    name = "apps.reviews"
    label = "reviews"
    verbose_name = "评阅"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
