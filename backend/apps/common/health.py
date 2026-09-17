from __future__ import annotations

import redis
from django.conf import settings
from django.db import connections
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .context import current_request_id
from .responses import success
from .storage import minio_health


@require_GET
def health(request: HttpRequest) -> HttpResponse:
    statuses = {
        "api": "up",
        "mysql": check_mysql(),
        "redis": check_redis(),
        "minio": minio_health(),
    }
    return JsonResponse(
        success(
            {"status": statuses, "ok": all(value == "up" for value in statuses.values())},
            current_request_id(),
        )
    )


def check_mysql() -> str:
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001
        return "down"
    return "up"


def check_redis() -> str:
    try:
        redis.Redis.from_url(settings.CACHES["default"]["LOCATION"]).ping()
    except Exception:  # noqa: BLE001
        return "down"
    return "up"
