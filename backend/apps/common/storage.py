from __future__ import annotations

from functools import lru_cache

import boto3
from botocore.client import Config
from django.conf import settings

from .constants import MINIO_PRESIGN_EXPIRE_SECONDS


@lru_cache(maxsize=1)
def minio_client():
    config = settings.MINIO
    scheme = "https" if config.secure else "http"
    return boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{config.endpoint}",
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def minio_health() -> str:
    try:
        minio_client().list_buckets()
    except Exception:  # noqa: BLE001
        return "down"
    return "up"


def presign_upload(bucket: str, object_key: str) -> str:
    return minio_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": object_key},
        ExpiresIn=MINIO_PRESIGN_EXPIRE_SECONDS,
    )


def presign_download(bucket: str, object_key: str) -> str:
    return minio_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": object_key},
        ExpiresIn=MINIO_PRESIGN_EXPIRE_SECONDS,
    )
