from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.response import Response


def get_trace_id(request: Any) -> str:
    """Return the trace ID attached by the request middleware."""
    return getattr(request, "trace_id", "")


def success_response(
    data: Any,
    request: Any,
    *,
    status_code: int = status.HTTP_200_OK,
    headers: dict[str, str] | None = None,
) -> Response:
    """Return a v2 detail success envelope."""
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
    """Return the v2 asynchronous 202 envelope with a Location header."""
    return success_response(
        data,
        request,
        status_code=status.HTTP_202_ACCEPTED,
        headers={"Location": location},
    )


def no_content_response() -> Response:
    """Return 204 only when an operation has no meaningful result body."""
    return Response(status=status.HTTP_204_NO_CONTENT)
