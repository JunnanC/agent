from __future__ import annotations

import logging
from typing import Any

from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from ..context import current_request_id
from ..errors import ApiError
from ..response.schema import error as error_schema
from .success import get_trace_id

logger = logging.getLogger(__name__)


def error_response(
    *,
    code: int | str,
    message: str,
    request: Any,
    status_code: int,
    detail: Any = None,
    retryable: bool = False,
) -> Response:
    return Response(
        error_schema(
            code,
            message,
            request_id=getattr(request, "request_id", "")
            or request.headers.get("X-Request-ID", "")
            or current_request_id(),
            trace_id=get_trace_id(request),
            detail=detail,
            retryable=retryable,
        ),
        status=status_code,
    )


def api_exception_handler(exc: Exception, context: dict[str, Any]):
    request = context.get("request")
    if isinstance(exc, ApiError):
        return error_response(
            code=exc.error.code,
            message=exc.error_message,
            request=request,
            status_code=exc.error.http_status,
            detail={"details": exc.details},
        )
    response = exception_handler(exc, context)
    if response is None:
        logger.error("Unhandled API exception", exc_info=exc)
        return error_response(
            code=50001,
            message="服务器内部错误",
            request=request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    code, message, retryable = _map_exception(exc, response.status_code)
    return error_response(
        code=code,
        message=message,
        request=request,
        status_code=response.status_code,
        detail=response.data,
        retryable=retryable,
    )


def _map_exception(exc: Exception, status_code: int) -> tuple[int | str, str, bool]:
    if isinstance(exc, ApiError):
        return exc.error.code, exc.error_message, False
    if isinstance(exc, exceptions.ValidationError):
        return 40001, "请求参数无效", False
    if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        return 40101, "需要登录", False
    if isinstance(exc, exceptions.PermissionDenied):
        return 40301, "无权执行此操作", False
    if isinstance(exc, exceptions.NotFound):
        return 40401, "资源不存在", False
    if isinstance(exc, exceptions.Throttled):
        return 42901, "请求过于频繁", True
    return f"HTTP_{status_code}", "请求失败", False


def _django_error(request: Any, *, code: int | str, message: str, status_code: int):
    from django.http import JsonResponse

    return JsonResponse(
        error_schema(
            code,
            message,
            request_id=request.headers.get("X-Request-ID", current_request_id()),
            trace_id=request.headers.get("X-Trace-ID", get_trace_id(request)),
        ),
        status=status_code,
    )


def bad_request_view(request: Any, exception=None):
    return _django_error(request, code=40001, message="请求无效", status_code=400)


def permission_denied_view(request: Any, exception=None):
    return _django_error(request, code=40301, message="无权执行此操作", status_code=403)


def not_found_view(request: Any, exception=None):
    return _django_error(request, code=40401, message="资源不存在", status_code=404)


def server_error_view(request: Any):
    logger.error("Unhandled Django server error")
    return _django_error(request, code=50001, message="服务器内部错误", status_code=500)
