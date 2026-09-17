from __future__ import annotations

from typing import Any

from django.http import HttpResponse


def success(data: Any, request_id: str) -> dict[str, Any]:
    return {"code": 0, "message": "ok", "data": data, "request_id": request_id}


def paginated(
    items: list[Any], page: int, page_size: int, total: int, request_id: str
) -> dict[str, Any]:
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
        },
        "request_id": request_id,
    }


def accepted(
    operation_id: str,
    trace_id: str,
    request_id: str,
    status: str = "ACCEPTED",
    estimated_records: int | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "operation_id": operation_id,
        "trace_id": trace_id,
        "status": status,
    }
    if estimated_records is not None:
        data["estimated_records"] = estimated_records
    return {
        "code": 0,
        "message": "accepted",
        "data": data,
        "request_id": request_id,
    }


def failure(
    code: int,
    message: str,
    request_id: str,
    details: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": {"details": details or []},
        "request_id": request_id,
    }


def json_response(payload: dict[str, Any], status: int = 200) -> HttpResponse:
    from django.http import JsonResponse

    return JsonResponse(payload, safe=False, status=status)
