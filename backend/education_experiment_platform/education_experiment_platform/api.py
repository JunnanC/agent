from typing import Any

from apps.core.errors import ApiError
from apps.core.responses import error_body
from django.http import HttpRequest, JsonResponse
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    request = context.get("request")
    trace_id = getattr(request, "trace_id", "")

    # 领域错误不继承 DRF 的 APIException，DRF 自己的处理器认不出它，
    # 默认会变成 500。这里先拦下，保证 doc 02 §八 的稳定 code、
    # HTTP 状态码和 doc 08 §1.5 的错误信封原样返回。
    if isinstance(exc, ApiError):
        return Response(
            error_body(exc.error, message=exc.message, detail=exc.detail, trace_id=trace_id),
            status=exc.error.http_status,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        return None
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
