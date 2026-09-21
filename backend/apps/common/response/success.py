from __future__ import annotations

import secrets
from typing import Any

from rest_framework import status
from rest_framework.response import Response

from apps.common.context import current_trace_id


def get_trace_id(request: Any) -> str:
    """Return or lazily create the trace ID for the current request."""
    trace_id = getattr(request, "trace_id", "") or current_trace_id()
    if not trace_id:
        trace_id = secrets.token_hex(16)
        request.trace_id = trace_id
    return trace_id


def success_response(
    data: Any,
    request: Any,
    *,
    status_code: int = status.HTTP_200_OK,
    headers: dict[str, str] | None = None,
) -> Response:
    """Return a API detail success envelope."""
    return Response(
        {"data": data, "meta": {"trace_id": get_trace_id(request)}},
        status=status_code,
        headers=headers,
    )


def created_response(
    data: Any,
    request: Any,
    *,
    location: str | None = None,
) -> Response:
    """Return a 201 response, optionally identifying the created resource."""
    headers = {"Location": location} if location else None
    return success_response(
        data,
        request,
        status_code=status.HTTP_201_CREATED,
        headers=headers,
    )


def accepted_response(
    data: Any,
    request: Any,
    *,
    location: str,
) -> Response:
    """Return the API asynchronous 202 envelope with a Location header."""
    return success_response(
        data,
        request,
        status_code=status.HTTP_202_ACCEPTED,
        headers={"Location": location},
    )


def no_content_response() -> Response:
    """Return 204 only when an operation has no meaningful result body."""
    return Response(status=status.HTTP_204_NO_CONTENT)
