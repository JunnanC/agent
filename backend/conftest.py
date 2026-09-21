from __future__ import annotations

import os

_TEST_ENV = {
    "DJANGO_SECRET_KEY": "test-secret",
    "REDIS_CACHE_URL": "redis://localhost:6379/0",
    "CELERY_BROKER_URL": "redis://localhost:6379/1",
    "MYSQL_HOST": "localhost",
    "MYSQL_PORT": "3306",
    "MYSQL_NAME": "agent",
    "MYSQL_USER": "agent",
    "MYSQL_PASSWORD": "test-password",
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ACCESS_KEY": "test-access",
    "MINIO_SECRET_KEY": "test-secret",
    "MINIO_SECURE": "false",
    "MINIO_GENERAL_BUCKET": "general",
    "MINIO_ARCHIVE_BUCKET": "archive",
    "MINIO_SNAPSHOT_BUCKET": "snapshot",
    "MINIO_EXPORT_BUCKET": "export",
}

for key, value in _TEST_ENV.items():
    os.environ.setdefault(key, value)
