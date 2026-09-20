from __future__ import annotations

import re
import secrets
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class TraceIdMiddleware:
    """Attach a validated trace ID to every request and response."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        supplied_trace_id = request.headers.get("X-Trace-ID", "")
        request.trace_id = (
            supplied_trace_id
            if TRACE_ID_PATTERN.fullmatch(supplied_trace_id)
            else secrets.token_hex(16)
        )
        response = self.get_response(request)
        response["X-Trace-ID"] = request.trace_id
        return response
