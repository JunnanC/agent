from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from django.http import HttpRequest, HttpResponse

from .constants import REQUEST_ID_HEADER, TRACE_ID_HEADER
from .context import RequestContext, current_request_id, reset_context, set_context
from .errors import INTERNAL_ERROR, ApiError, error_response
from .logging import json_log
from .providers import actor_identifier


def _request_context(request: HttpRequest) -> RequestContext:
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
    trace_id = request.headers.get(TRACE_ID_HEADER) or str(uuid.uuid4())
    return RequestContext(
        request_id=request_id,
        trace_id=trace_id,
        user_id=actor_identifier(request),
        action=request.method,
    )


class RequestTraceMiddleware:
    async_capable = True
    sync_capable = True

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse:
        if isinstance(exception, ApiError):
            return error_response(
                exception.error,
                current_request_id(),
                details=exception.details,
                message=exception.error_message,
            )
        return error_response(INTERNAL_ERROR, current_request_id())

    def __call__(self, request: HttpRequest) -> HttpResponse:
        started = time.monotonic()
        context = _request_context(request)
        token = set_context(context)
        try:
            response = self.get_response(request)
            json_log(
                "request.completed",
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
            )
        except Exception as exc:  # noqa: BLE001
            json_log(
                "request.failed",
                level=40,
                method=request.method,
                path=request.path,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
            )
            if isinstance(exc, ApiError):
                response = error_response(
                    exc.error,
                    context.request_id,
                    details=exc.details,
                    message=exc.error_message,
                )
            else:
                response = error_response(INTERNAL_ERROR, context.request_id)
            json_log(
                "request.completed",
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
            )
        finally:
            reset_context(token)
        response[REQUEST_ID_HEADER] = context.request_id
        response[TRACE_ID_HEADER] = context.trace_id
        return response

    async def __acall__(self, request: HttpRequest) -> HttpResponse:
        started = time.monotonic()
        context = _request_context(request)
        token = set_context(context)
        try:
            response = await self._async_get_response(request)
            json_log(
                "request.completed",
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
            )
        except Exception as exc:  # noqa: BLE001
            json_log(
                "request.failed",
                level=40,
                method=request.method,
                path=request.path,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
            )
            if isinstance(exc, ApiError):
                response = error_response(
                    exc.error,
                    context.request_id,
                    details=exc.details,
                    message=exc.error_message,
                )
            else:
                response = error_response(INTERNAL_ERROR, context.request_id)
            json_log(
                "request.completed",
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
            )
        finally:
            reset_context(token)
        response[REQUEST_ID_HEADER] = context.request_id
        response[TRACE_ID_HEADER] = context.trace_id
        return response

    async def _async_get_response(self, request: HttpRequest) -> HttpResponse:
        result: Any = self.get_response(request)
        if isinstance(result, Awaitable):
            return await result
        return result
