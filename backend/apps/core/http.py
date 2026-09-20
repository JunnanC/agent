import uuid

from django.http import JsonResponse
from rest_framework.response import Response


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict,
    request,
) -> Response:
    trace_id = getattr(request, "trace_id", "") or str(uuid.uuid4())
    return Response(
        {
            "code": code,
            "message": message,
            "details": details,
            "trace_id": trace_id,
        },
        status=status_code,
    )


def not_implemented(request, slice_id: str, route: str) -> Response:
    return error_response(
        status_code=501,
        code="NOT_IMPLEMENTED",
        message="路由已登记，当前切片未实现",
        details={"slice": slice_id, "route": route},
        request=request,
    )


def idempotency_key_required(request, route: str) -> Response:
    trace_id = getattr(request, "trace_id", "") or str(uuid.uuid4())
    return JsonResponse(
        {
            "code": "IDEMPOTENCY_KEY_REQUIRED",
            "message": "该写操作必须提供 Idempotency-Key 请求头",
            "details": {"header": "Idempotency-Key", "route": route},
            "trace_id": trace_id,
        },
        status=400,
    )
