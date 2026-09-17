from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class MinIOConfig:
    endpoint: str
    access_key: str
    secret_key: str
    secure: bool
    general_bucket: str
    archive_bucket: str
    snapshot_bucket: str
    export_bucket: str


def require_str(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return value


def optional_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"Environment variable {name} must be a boolean")


def validate_redis_separation(cache_url: str, broker_url: str) -> None:
    cache_path = urlparse(cache_url).path or "/0"
    broker_path = urlparse(broker_url).path or "/0"
    cache_db = cache_path.rstrip("/").rpartition("/")[2]
    broker_db = broker_path.rstrip("/").rpartition("/")[2]
    if cache_db != "0" or broker_db != "1":
        raise ConfigurationError(
            "Redis logical databases must stay separated: REDIS_CACHE_URL db 0, "
            "CELERY_BROKER_URL db 1"
        )


def load_environment() -> dict[str, object]:
    cache_url = require_str("REDIS_CACHE_URL")
    broker_url = require_str("CELERY_BROKER_URL")
    validate_redis_separation(cache_url, broker_url)

    return {
        "SECRET_KEY": require_str("DJANGO_SECRET_KEY"),
        "DEBUG": optional_bool("DJANGO_DEBUG", False),
        "MYSQL_HOST": require_str("MYSQL_HOST"),
        "MYSQL_PORT": int(require_str("MYSQL_PORT")),
        "MYSQL_NAME": require_str("MYSQL_NAME"),
        "MYSQL_USER": require_str("MYSQL_USER"),
        "MYSQL_PASSWORD": require_str("MYSQL_PASSWORD"),
        "REDIS_CACHE_URL": cache_url,
        "CELERY_BROKER_URL": broker_url,
        "MINIO": MinIOConfig(
            endpoint=require_str("MINIO_ENDPOINT"),
            access_key=require_str("MINIO_ACCESS_KEY"),
            secret_key=require_str("MINIO_SECRET_KEY"),
            secure=optional_bool("MINIO_SECURE", False),
            general_bucket=require_str("MINIO_GENERAL_BUCKET"),
            archive_bucket=require_str("MINIO_ARCHIVE_BUCKET"),
            snapshot_bucket=require_str("MINIO_SNAPSHOT_BUCKET"),
            export_bucket=require_str("MINIO_EXPORT_BUCKET"),
        ),
    }


ENV = load_environment()
