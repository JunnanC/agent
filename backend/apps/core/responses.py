from __future__ import annotations

from typing import Any

from django.http import HttpResponse, JsonResponse

from .response.schema import accepted as _accepted
from .response.schema import failure as _failure
from .response.schema import paginated as _paginated
from .response.schema import success as _success


def _trace_id() -> str:
    from .context import current_trace_id

    return current_trace_id()


def success(data: Any, request_id: str, trace_id: str | None = None) -> dict[str, Any]:
    return _success(data, request_id=request_id, trace_id=trace_id or _trace_id())


def paginated(
    items: list[Any],
    page: int,
    page_size: int,
    total: int,
    request_id: str,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return _paginated(
        items,
        page=page,
        page_size=page_size,
        total=total,
        request_id=request_id,
        trace_id=trace_id or _trace_id(),
    )


def accepted(
    operation_id: str,
    trace_id: str,
    request_id: str,
    status: str = "ACCEPTED",
    estimated_records: int | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {"operation_id": operation_id, "status": status}
    if estimated_records is not None:
        data["estimated_records"] = estimated_records
    return _accepted(data, request_id=request_id, trace_id=trace_id)


def failure(
    code: int | str,
    message: str,
    request_id: str,
    details: list[dict[str, Any]] | None = None,
    *,
    retryable: bool = False,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return _failure(
        code,
        message,
        request_id,
        details,
        trace_id=trace_id or _trace_id(),
        retryable=retryable,
    )


def json_response(payload: dict[str, Any], status: int = 200) -> HttpResponse:
    return JsonResponse(payload, safe=False, status=status)
