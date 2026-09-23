from __future__ import annotations

import secrets
from typing import Any

from rest_framework import status
from rest_framework.response import Response

from ..context import current_request_id, current_trace_id
from .schema import success


def get_trace_id(request: Any) -> str:
    trace_id = getattr(request, "trace_id", "") or current_trace_id()
    if not trace_id:
        trace_id = secrets.token_hex(16)
        request.trace_id = trace_id
    return trace_id


def _request_id(request: Any) -> str:
    return (
        getattr(request, "request_id", "")
        or request.headers.get("X-Request-ID", "")
        or current_request_id()
    )


def success_response(
    data: Any,
    request: Any,
    *,
    status_code: int = status.HTTP_200_OK,
    headers: dict[str, str] | None = None,
    **meta: Any,
) -> Response:
    return Response(
        success(
            data,
            request_id=_request_id(request),
            trace_id=get_trace_id(request),
            **meta,
        ),
        status=status_code,
        headers=headers,
    )


def created_response(data: Any, request: Any, *, location: str | None = None) -> Response:
    headers = {"Location": location} if location else None
    return success_response(data, request, status_code=status.HTTP_201_CREATED, headers=headers)


def accepted_response(data: Any, request: Any, *, location: str) -> Response:
    return success_response(
        data,
        request,
        status_code=status.HTTP_202_ACCEPTED,
        headers={"Location": location},
    )


def no_content_response(request: Any | None = None) -> Response:
    """Return a body-bearing success so every JSON response has one envelope."""
    if request is None:
        return Response(
            {
                "data": None,
                "meta": {"message": "ok", "request_id": "", "trace_id": ""},
                "error": None,
            }
        )
    return success_response(None, request)
