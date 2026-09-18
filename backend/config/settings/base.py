from __future__ import annotations

from pathlib import Path

from config.env import ENV

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = str(ENV["SECRET_KEY"])
DEBUG = bool(ENV["DEBUG"])
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.common",
    "apps.identity",
    "apps.membership",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.common.middleware.RequestTraceMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": ENV["MYSQL_HOST"],
        "PORT": ENV["MYSQL_PORT"],
        "NAME": ENV["MYSQL_NAME"],
        "USER": ENV["MYSQL_USER"],
        "PASSWORD": ENV["MYSQL_PASSWORD"],
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET SESSION time_zone = '+00:00'",
        },
        "TEST": {"CHARSET": "utf8mb4"},
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": ENV["REDIS_CACHE_URL"],
    }
}

CELERY_BROKER_URL = str(ENV["CELERY_BROKER_URL"])
CELERY_RESULT_BACKEND = str(ENV["CELERY_BROKER_URL"])
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "EXCEPTION_HANDLER": "apps.common.errors.drf_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
}

TIME_ZONE = "UTC"
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MINIO = ENV["MINIO"]

COMMON_PRINCIPAL_PERMISSION_PROVIDER = (
    "apps.identity.services.permissions.IdentityPrincipalPermissionProvider"
)
COMMON_AUDITABLE_ACTOR_PROVIDER = "apps.identity.services.auth.IdentityAuditableActorProvider"
IDENTITY_MEMBERSHIP_PROVIDER = "apps.membership.identity_provider.MembershipIdentityProvider"
COMMON_IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60
COMMON_OUTBOX_BATCH_SIZE = 100
COMMON_AUDIT_EXPORT_MAX_RECORDS = 100_000
COMMON_AUDIT_EXPORT_TTL_SECONDS = 24 * 60 * 60
