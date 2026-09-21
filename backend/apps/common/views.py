from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .audit import AuditQueryFilters, build_audit_queryset
from .audit_export import create_audit_export, get_export_state
from .constants import IDEMPOTENCY_KEY_HEADER
from .context import current_request_id
from .errors import RESOURCE_NOT_FOUND, VALIDATION_ERROR, ApiError
from .idempotency import idempotent
from .pagination import paginate_queryset, parse_page_params
from .permissions import require_system_admin
from .providers import actor_identifier, actor_role
from .responses import accepted, paginated, success
from .serializers import AuditExportSerializer, parse_datetime


def _query_params(request: HttpRequest) -> Any:
    return request.query_params if hasattr(request, "query_params") else request.GET


def _filters_from_request(request: HttpRequest) -> AuditQueryFilters:
    params = _query_params(request)
    return AuditQueryFilters(
        user_id=params.get("user_id") or None,
        action=params.get("action") or None,
        resource_type=params.get("resource_type") or None,
        resource_id=params.get("resource_id") or None,
        request_id=params.get("request_id") or None,
        trace_id=params.get("trace_id") or None,
        assignment_id=params.get("assignment_id") or None,
        instance_id=params.get("instance_id") or None,
        ip_address=params.get("ip_address") or None,
        created_after=parse_datetime(params.get("created_after")),
        created_before=parse_datetime(params.get("created_before")),
    )


def _serialize_audit(log: Any) -> dict[str, Any]:
    return {
        "id": log.id,
        "actor_user_id": log.actor_user_id,
        "actor_role_code": log.actor_role_code,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "assignment_id": log.assignment_id,
        "instance_id": log.instance_id,
        "trace_id": log.trace_id,
        "request_id": log.request_id,
        "idempotency_key": log.idempotency_key,
        "result": log.result,
        "reason": log.reason,
        "before_json": log.before_json,
        "after_json": log.after_json,
        "ip_address": log.ip,
        "user_agent_hash": log.user_agent_hash,
        "occurred_at": log.occurred_at.isoformat(),
        "created_at": log.created_at.isoformat(),
    }


@require_GET
def audit_logs(request: HttpRequest) -> HttpResponse:
    require_system_admin(request)
    filters = _filters_from_request(request)
    params = parse_page_params(
        request, {"created_at", "occurred_at", "action", "actor_user_id"}, "created_at"
    )
    result = paginate_queryset(build_audit_queryset(filters), params, "created_at")
    return JsonResponse(
        paginated(
            [_serialize_audit(log) for log in result.items],
            result.page,
            result.page_size,
            result.total,
            current_request_id(),
        )
    )


def _request_json(request: HttpRequest) -> dict[str, Any]:
    try:
        value = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        raise ApiError(VALIDATION_ERROR, message="请求体必须为JSON对象") from exc
    if not isinstance(value, dict):
        raise ApiError(VALIDATION_ERROR, message="请求体必须为JSON对象")
    return value


@csrf_exempt
@require_POST
@idempotent("audit-export")
def export_audit_logs(request: HttpRequest) -> HttpResponse:
    require_system_admin(request)
    serializer = AuditExportSerializer(data=_request_json(request))
    if not serializer.is_valid():
        details = [
            {"field": str(field), "issue": str(error)}
            for field, errors in serializer.errors.items()
            for error in errors
        ]
        raise ApiError(VALIDATION_ERROR, details=details)

    validated = serializer.validated_data
    filter_values = validated["filters"]
    filters = AuditQueryFilters(
        user_id=filter_values.get("user_id") or None,
        action=filter_values.get("action") or None,
        resource_type=filter_values.get("resource_type") or None,
        resource_id=filter_values.get("resource_id") or None,
        request_id=filter_values.get("request_id") or None,
        trace_id=filter_values.get("trace_id") or None,
        assignment_id=filter_values.get("assignment_id") or None,
        instance_id=filter_values.get("instance_id") or None,
        ip_address=filter_values.get("ip_address") or None,
        created_after=filter_values.get("created_after"),
        created_before=filter_values.get("created_before"),
    )
    state = create_audit_export(
        filters=filters,
        export_format=validated["format"],
        mask_fields=validated["mask_fields"],
        actor_user_id=actor_identifier(request),
        actor_role_code=actor_role(request),
        idempotency_key=request.headers.get(IDEMPOTENCY_KEY_HEADER),
        request_id=current_request_id(),
    )
    return JsonResponse(
        accepted(
            str(state["operation_id"]),
            str(state["trace_id"]),
            current_request_id(),
            str(state["status"]),
            estimated_records=int(state["estimated_records"]),
        ),
        status=202,
    )


@require_GET
def audit_export_status(request: HttpRequest, operation_id: str) -> HttpResponse:
    require_system_admin(request)
    state = get_export_state(operation_id)
    if state is None:
        raise ApiError(RESOURCE_NOT_FOUND)
    return JsonResponse(success(state, current_request_id()))
