from __future__ import annotations

from typing import Any

from rest_framework.response import Response


def get_trace_id(request: Any) -> str:
    return getattr(request, "trace_id", "")


def success_response(data: Any, request: Any, *, status_code: int = 200) -> Response:
    return Response(
        {"data": data, "meta": {"trace_id": get_trace_id(request)}},
        status=status_code,
    )


def error_response(
    *,
    code: str,
    message: str,
    request: Any,
    status_code: int,
    detail: Any = None,
    retryable: bool = False,
) -> Response:
    return Response(
        {
            "error": {
                "code": code,
                "message": message,
                "detail": {} if detail is None else detail,
                "trace_id": get_trace_id(request),
                "retryable": retryable,
            }
        },
        status=status_code,
    )
