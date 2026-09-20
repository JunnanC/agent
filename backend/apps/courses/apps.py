from django.apps import AppConfig


class CoursesAppConfig(AppConfig):
    name = "apps.courses"
    label = "courses"
    verbose_name = "课程"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        return None
