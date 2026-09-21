import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    file_path = os.getenv(f"{name}_FILE")
    value: str | None
    if file_path:
        value = Path(file_path).read_text(encoding="utf-8").strip()
    else:
        value = os.getenv(name)
        if value is None:
            value = default
    if required and not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value or ""


def csv_env(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY", "unsafe-local-only-key-change-before-deploy")
DEBUG = False
ALLOWED_HOSTS = csv_env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,django")
CSRF_TRUSTED_ORIGINS = csv_env("DJANGO_TRUSTED_ORIGINS")

APP_VERSION = env("APP_VERSION", "0.1.0-p00")
OPENAPI_REVISION = env("OPENAPI_REVISION", "v2-p00")
GIT_REVISION = env("GIT_REVISION", "development")
BUILD_TIME = env("BUILD_TIME", "development")
TRUSTED_PROXY_CIDRS = csv_env(
    "TRUSTED_PROXY_CIDRS",
    "127.0.0.0/8",
)

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.core.apps.CoreConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.courses.apps.CoursesConfig",
    "apps.governance.apps.GovernanceConfig",
    "apps.labtemplates.apps.LabTemplatesConfig",
    "apps.experiments.apps.ExperimentsConfig",
    "apps.provisioning.apps.ProvisioningConfig",
    "apps.workspaces.apps.WorkspacesConfig",
    "apps.reports.apps.ReportsConfig",
    "apps.reviews.apps.ReviewsConfig",
    "apps.archives.apps.ArchivesConfig",
    "apps.agents.apps.AgentsConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.analytics.apps.AnalyticsConfig",
    "apps.integrations.apps.IntegrationsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "education_experiment_platform.middleware.TraceContextMiddleware",
    "education_experiment_platform.middleware.ProxyContextMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "education_experiment_platform.urls"
ASGI_APPLICATION = "education_experiment_platform.asgi.application"
WSGI_APPLICATION = "education_experiment_platform.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("MYSQL_DATABASE", "edu_platform"),
        "USER": env("MYSQL_USER", "edu_platform"),
        "PASSWORD": env("MYSQL_PASSWORD", ""),
        "HOST": env("MYSQL_HOST", "mysql"),
        "PORT": env("MYSQL_PORT", "3306"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK: dict[str, object] = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "education_experiment_platform.api.exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS: dict[str, object] = {
    "TITLE": "Education Agent Platform API",
    "DESCRIPTION": "P00 infrastructure contract. Business operations are added in later stages.",
    "VERSION": OPENAPI_REVISION,
    "SERVE_INCLUDE_SCHEMA": False,
    "OAS_VERSION": "3.0.3",
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://redis:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://redis:6379/2")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.provisioning.*": {"queue": "runtime"},
    "apps.archives.*": {"queue": "archive"},
    "apps.notifications.*": {"queue": "notifications"},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "education_experiment_platform.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_DOMAIN = None
