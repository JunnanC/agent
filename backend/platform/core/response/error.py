from __future__ import annotations

from typing import Any

from rest_framework.response import Response

from core.response.success import get_trace_id


def error_response(
    *,
    code: str,
    message: str,
    request: Any,
    status_code: int,
    detail: Any = None,
    retryable: bool = False,
) -> Response:
    """Return the stable v2 error envelope."""
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
