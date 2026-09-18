from __future__ import annotations

from celery import shared_task

from .services.admin_users import create_user, parse_import_csv


@shared_task
def import_users(actor_id: int, import_file_key: str) -> None:
    from django.conf import settings

    from apps.common.storage import minio_client

    content = (
        minio_client()
        .get_object(Bucket=settings.MINIO.general_bucket, Key=import_file_key)["Body"]
        .read()
    )
    rows = parse_import_csv(content)
    for row in rows:
        create_user(actor_id, {**row, "role_id": int(row["role_id"])})
