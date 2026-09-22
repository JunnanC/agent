from __future__ import annotations

"""Framework-neutral response schemas.

Every response has exactly the same top-level shape.  HTTP status is carried
by the transport, not duplicated in JSON:

    {"data": ..., "meta": {...}, "error": null}
    {"data": null, "meta": {...}, "error": {...}}

The helpers return plain dictionaries so Django, DRF, SSE adapters, and
future workers can use the same contract without importing one another.
"""

from typing import Any

from ..masking import mask_sensitive


def _meta(request_id: str, *, trace_id: str | None = None, **extra: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"request_id": request_id, "trace_id": trace_id or ""}
    value.update(extra)
    return value


def success(
    data: Any,
    *,
    request_id: str,
    trace_id: str | None = None,
    message: str = "ok",
    **meta: Any,
) -> dict[str, Any]:
    return {
        "data": data,
        "meta": _meta(request_id, trace_id=trace_id, message=message, **meta),
        "error": None,
    }


def paginated(
    items: list[Any],
    *,
    page: int,
    page_size: int,
    total: int,
    request_id: str,
    trace_id: str | None = None,
    **meta: Any,
) -> dict[str, Any]:
    return success(
        {"items": items, "page": page, "page_size": page_size, "total": total},
        request_id=request_id,
        trace_id=trace_id,
        **meta,
    )


def accepted(
    data: dict[str, Any],
    *,
    request_id: str,
    trace_id: str,
    **meta: Any,
) -> dict[str, Any]:
    return success(
        data,
        request_id=request_id,
        trace_id=trace_id,
        **meta,
    )


def error(
    code: int | str,
    message: str,
    *,
    request_id: str,
    trace_id: str | None = None,
    detail: Any = None,
    retryable: bool = False,
    **meta: Any,
) -> dict[str, Any]:
    return {
        "data": None,
        "meta": _meta(request_id, trace_id=trace_id, **meta),
        "error": {
            "code": code,
            "message": message,
            "detail": {} if detail is None else mask_sensitive(detail),
            "retryable": retryable,
        },
    }


def failure(
    code: int | str,
    message: str,
    request_id: str,
    details: list[dict[str, Any]] | None = None,
    *,
    trace_id: str | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
    """Compatibility spelling for callers that call errors failures."""
    return error(
        code,
        message,
        request_id=request_id,
        trace_id=trace_id,
        detail={"details": details or []},
        retryable=retryable,
    )
