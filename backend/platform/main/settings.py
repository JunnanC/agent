"""Django settings for the v2 platform API."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    return os.getenv(name, str(default)).strip().lower() in {
        "1", "true", "yes", "on",
    }


def env_list(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


APP_ENV = os.getenv("APP_ENV", "local").strip().lower()
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-development-only")
if APP_ENV != "local" and SECRET_KEY == "local-development-only":
    raise RuntimeError("DJANGO_SECRET_KEY must be set outside the local environment")

DEBUG = env_bool("DJANGO_DEBUG", APP_ENV == "local")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
    "runtime",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "main.urls"

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

WSGI_APPLICATION = "main.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "agent_virtual_lab_v2"),
        "USER": os.getenv("MYSQL_USER", "agent_platform"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
        "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "CONN_MAX_AGE": int(os.getenv("MYSQL_CONN_MAX_AGE", "60")),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "core.response.error.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "core.response.pagination.StandardPagination",
    "PAGE_SIZE": 20,
}

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "600"))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "540"))
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if APP_ENV == "production":
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

MAILERS = {
    "default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"},
}
