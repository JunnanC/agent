import ipaddress
import os
from datetime import datetime, timezone
from pathlib import Path

import pymysql


pymysql.install_as_MySQLdb()


BASE_DIR = Path(__file__).resolve().parents[2]


def env_list(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def trusted_networks(name: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for value in env_list(name):
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError as exc:
            raise RuntimeError(f"Invalid network in {name}: {value}") from exc
    return networks


SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is required; refusing to start with a default value")

DEBUG = False
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "django_celery_beat",
    "apps.core.apps.CoreAppConfig",
    "apps.accounts.apps.AccountsAppConfig",
    "apps.courses.apps.CoursesAppConfig",
    "apps.labtemplates.apps.LabtemplatesAppConfig",
    "apps.experiments.apps.ExperimentsAppConfig",
    "apps.provisioning.apps.ProvisioningAppConfig",
    "apps.workspaces.apps.WorkspacesAppConfig",
    "apps.reports.apps.ReportsAppConfig",
    "apps.reviews.apps.ReviewsAppConfig",
    "apps.archives.apps.ArchivesAppConfig",
    "apps.agents.apps.AgentsAppConfig",
    "apps.governance.apps.GovernanceAppConfig",
    "apps.notifications.apps.NotificationsAppConfig",
]

MIDDLEWARE = [
    "apps.core.middleware.PortalContextMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "education_experiment_platform.urls"
ASGI_APPLICATION = "education_experiment_platform.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("MYSQL_DATABASE", ""),
        "USER": os.environ.get("MYSQL_USER", ""),
        "PASSWORD": os.environ.get("MYSQL_PASSWORD", ""),
        "HOST": os.environ.get("MYSQL_HOST", ""),
        "PORT": os.environ.get("MYSQL_PORT", ""),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

SERVICE_NAME = os.environ.get("SERVICE_NAME", "django")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_sensitive": {
            "()": "apps.core.logging.SensitiveDataFilter",
        },
    },
    "formatters": {
        "json": {
            "()": "apps.core.logging.StructuredJsonFormatter",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "filters": ["redact_sensitive"],
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["stdout"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["stdout"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Education Experiment Platform API",
    "VERSION": "2.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "EXTENSIONS_INFO": {
        "x-openapi-revision": "2026-09-20.b6-pending-freeze",
        "x-generated-at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "x-contract-status": "pending-freeze; replace after contract freeze",
    },
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "apps.core.schema.add_trace_response_header",
    ],
}

CELERY_BROKER_URL = os.environ.get("REDIS_URL", "")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "")
CELERY_TASK_DEFAULT_QUEUE = "q_default"
CELERY_TASK_QUEUES = {
    "q_default": None,
    "q_relay": None,
    "q_provision": None,
    "q_archive": None,
    "q_compensate": None,
}

PORTAL_TRUSTED_PROXY_NETWORKS = trusted_networks("PORTAL_TRUSTED_PROXY_NETWORKS")
PORTAL_HOST_MAP = {
    "USER": env_list("PORTAL_USER_HOSTS"),
    "TEACHING": env_list("PORTAL_TEACHING_HOSTS"),
    "PLATFORM": env_list("PORTAL_PLATFORM_HOSTS"),
}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
