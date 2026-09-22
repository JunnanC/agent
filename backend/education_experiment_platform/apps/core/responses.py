"""响应信封与分页（doc 08 §1.1、§1.3、§1.4）。

成功：``{"data": ..., "meta": {"trace_id": ...}}``
列表：``meta`` 追加 ``page`` / ``page_size`` / ``total``
异步：202 + ``Location`` + ``job_id`` / ``subject_id`` / ``events_channel``

信封只在这里构造，视图不拼 JSON，避免出现第二种信封形状。
"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from rest_framework.response import Response

from .errors import VALIDATION_ERROR, ApiError, ErrorCode

PAGE_SIZE_DEFAULT = 20
# doc 08 §1.1：page_size 上限 100。上限存在的意义是防止一次请求拉崩数据库，
# 不是防止客户端出错，所以越界直接拒绝而不是静默截断。
PAGE_SIZE_MAX = 100


def trace_id_of(request: HttpRequest) -> str:
    return str(getattr(request, "trace_id", "") or "")


def parse_page_params(request: HttpRequest) -> tuple[int, int]:
    page = _positive_int(request, "page", 1)
    page_size = _positive_int(request, "page_size", PAGE_SIZE_DEFAULT)
    if page_size > PAGE_SIZE_MAX:
        raise ApiError(
            VALIDATION_ERROR,
            detail={"field": "page_size", "issue": f"不得超过 {PAGE_SIZE_MAX}"},
        )
    return page, page_size


def success(
    data: Any, request: HttpRequest, *, status: int = 200, etag: str | None = None
) -> Response:
    response = Response({"data": data, "meta": {"trace_id": trace_id_of(request)}}, status=status)
    if etag is not None:
        response["ETag"] = etag
    return response


def paginated(
    items: list[Any],
    request: HttpRequest,
    *,
    page: int,
    page_size: int,
    total: int,
    etag: str | None = None,
) -> Response:
    response = Response({
        "data": items,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "trace_id": trace_id_of(request),
        },
    })
    if etag is not None:
        response["ETag"] = etag
    return response


def accepted(
    data: dict[str, Any], request: HttpRequest, *, location: str | None = None
) -> Response:
    response = Response({"data": data, "meta": {"trace_id": trace_id_of(request)}}, status=202)
    if location:
        response["Location"] = location
    return response


def error_body(
    error: ErrorCode, *, message: str, detail: dict[str, Any], trace_id: str
) -> dict[str, Any]:
    """错误信封。与 api.exception_handler 共用，保证两条路径形状一致。"""
    return {
        "error": {
            "code": error.code,
            "message": message,
            "detail": detail,
            "trace_id": trace_id,
            "retryable": error.retryable,
        }
    }


def _positive_int(request: HttpRequest, name: str, default: int) -> int:
    raw = request.query_params.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ApiError(VALIDATION_ERROR, detail={"field": name, "issue": "必须是整数"}) from exc
    if value < 1:
        raise ApiError(VALIDATION_ERROR, detail={"field": name, "issue": "必须大于 0"})
    return value
