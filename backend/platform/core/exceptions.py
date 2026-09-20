from __future__ import annotations

import logging
from typing import Any

from django.http import HttpRequest, JsonResponse
from rest_framework import exceptions, status
from rest_framework.views import exception_handler

from core.response import error_response, get_trace_id

logger = logging.getLogger(__name__)


class ApiError(exceptions.APIException):
    """Base exception for stable, client-facing API failures."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "API_ERROR"
    default_detail = "请求失败"
    retryable = False

    def __init__(
        self,
        detail: Any = None,
        *,
        code: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(detail=detail, code=code)
        if retryable is not None:
            self.retryable = retryable


def api_exception_handler(exc: Exception, context: dict[str, Any]):
    request = context.get("request")
    response = exception_handler(exc, context)
    if response is None:
        logger.error(
            "Unhandled API exception",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"trace_id": get_trace_id(request)},
        )
        return error_response(
            code="INTERNAL_ERROR",
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


def _map_exception(exc: Exception, status_code: int) -> tuple[str, str, bool]:
    if isinstance(exc, ApiError):
        codes = exc.get_codes()
        code = codes if isinstance(codes, str) else exc.default_code
        return str(code), str(exc.detail), exc.retryable
    if isinstance(exc, exceptions.ValidationError):
        return "VALIDATION_ERROR", "请求参数无效", False
    if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        return "AUTH_REQUIRED", "需要登录", False
    if isinstance(exc, exceptions.PermissionDenied):
        return "PORTAL_ACCESS_DENIED", "无权执行此操作", False
    if isinstance(exc, exceptions.NotFound):
        return "RESOURCE_NOT_FOUND", "资源不存在", False
    if isinstance(exc, exceptions.Throttled):
        return "RATE_LIMITED", "请求过于频繁", True
    return f"HTTP_{status_code}", "请求失败", False


def _django_error(
    request: HttpRequest,
    *,
    code: str,
    message: str,
    status_code: int,
) -> JsonResponse:
    return JsonResponse(
        {
            "error": {
                "code": code,
                "message": message,
                "detail": {},
                "trace_id": get_trace_id(request),
                "retryable": False,
            }
        },
        status=status_code,
    )


def bad_request_view(request: HttpRequest, exception=None) -> JsonResponse:
    return _django_error(
        request, code="VALIDATION_ERROR", message="请求无效", status_code=400,
    )


def permission_denied_view(request: HttpRequest, exception=None) -> JsonResponse:
    return _django_error(
        request, code="PORTAL_ACCESS_DENIED", message="无权执行此操作", status_code=403,
    )


def not_found_view(request: HttpRequest, exception=None) -> JsonResponse:
    return _django_error(
        request, code="RESOURCE_NOT_FOUND", message="资源不存在", status_code=404,
    )


def server_error_view(request: HttpRequest) -> JsonResponse:
    logger.error(
        "Unhandled Django server error",
        extra={"trace_id": get_trace_id(request)},
    )
    return _django_error(
        request, code="INTERNAL_ERROR", message="服务器内部错误", status_code=500,
    )
