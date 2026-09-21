from typing import Any

from django.http import HttpRequest, JsonResponse
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    request = context.get("request")
    trace_id = getattr(request, "trace_id", "")
    detail = response.data
    response.data = {
        "error": {
            "code": "VALIDATION_ERROR" if response.status_code == 400 else "REQUEST_FAILED",
            "message": "请求无法处理",
            "detail": detail,
            "trace_id": trace_id,
            "retryable": False,
        }
    }
    return response


def api_not_found(request: HttpRequest, _path: str = "") -> JsonResponse:
    return JsonResponse(
        {
            "error": {
                "code": "RESOURCE_NOT_FOUND",
                "message": "资源不存在",
                "detail": {},
                "trace_id": getattr(request, "trace_id", ""),
                "retryable": False,
            }
        },
        status=404,
    )
