from __future__ import annotations

import csv
import io
import json
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task
from django.conf import settings
from django.db import transaction

from .audit import AuditQueryFilters, AuditRecord, build_audit_queryset, mask_ip, record_audit
from .constants import AUDIT_EXPORT_TTL_SECONDS
from .context import current_trace_id
from .errors import AUDIT_EXPORT_TOO_LARGE, EMPTY_FILTER, ApiError
from .idempotency import redis_client
from .logging import mask_sensitive
from .models import AuditLog
from .serializers import parse_datetime
from .storage import minio_client, presign_download

EXPORT_FIELDS = [
    "id",
    "actor_user_id",
    "actor_role_code",
    "action",
    "target_type",
    "target_id",
    "assignment_id",
    "instance_id",
    "trace_id",
    "request_id",
    "idempotency_key",
    "result",
    "reason",
    "before_json",
    "after_json",
    "ip_address",
    "user_agent",
    "occurred_at",
    "created_at",
]


def filters_from_payload(payload: dict[str, Any]) -> AuditQueryFilters:
    return AuditQueryFilters(
        user_id=payload.get("user_id") or None,
        action=payload.get("action") or None,
        resource_type=payload.get("resource_type") or None,
        resource_id=payload.get("resource_id") or None,
        request_id=payload.get("request_id") or None,
        trace_id=payload.get("trace_id") or None,
        assignment_id=payload.get("assignment_id") or None,
        instance_id=payload.get("instance_id") or None,
        ip_address=payload.get("ip_address") or None,
        created_after=parse_datetime(payload.get("created_after")),
        created_before=parse_datetime(payload.get("created_before")),
    )


def has_filters(filters: AuditQueryFilters) -> bool:
    return any(value is not None and value != "" for value in vars(filters).values())


def export_state_key(operation_id: str) -> str:
    return f"audit-export:{operation_id}"


def save_export_state(state: dict[str, Any]) -> None:
    redis_client().set(
        export_state_key(str(state["operation_id"])),
        json.dumps(state, ensure_ascii=False, default=str),
        ex=AUDIT_EXPORT_TTL_SECONDS,
    )


def get_export_state(operation_id: str) -> dict[str, Any] | None:
    raw = redis_client().get(export_state_key(operation_id))
    if raw is None:
        return None
    value = json.loads(raw)
    return value if isinstance(value, dict) else None


def create_audit_export(
    *,
    filters: AuditQueryFilters,
    export_format: str,
    mask_fields: list[str],
    actor_user_id: str | None,
    actor_role_code: str | None,
    idempotency_key: str | None,
    request_id: str,
) -> dict[str, Any]:
    if not has_filters(filters):
        raise ApiError(
            EMPTY_FILTER,
            message="筛选条件不能为空",
            details=[{"field": "filters", "issue": "至少需要一个筛选条件"}],
        )

    operation_id = str(uuid.uuid4())
    trace_id = current_trace_id()
    accepted_at = datetime.now(UTC)
    filter_payload = {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in vars(filters).items()
        if value is not None
    }
    state: dict[str, Any] = {
        "operation_id": operation_id,
        "trace_id": trace_id,
        "status": "ACCEPTED",
        "format": export_format,
        "masked_fields": mask_fields,
        "accepted_at": accepted_at.isoformat(),
        "expires_at": (accepted_at + timedelta(seconds=AUDIT_EXPORT_TTL_SECONDS)).isoformat(),
        "actor_user_id": actor_user_id,
        "actor_role_code": actor_role_code,
        "idempotency_key": idempotency_key,
        "request_id": request_id,
        "filters": filter_payload,
    }
    with transaction.atomic():
        record_audit(
            AuditRecord(
                actor_user_id=actor_user_id,
                actor_role_code=actor_role_code,
                action="audit_export.requested",
                target_type="USER",
                target_id=actor_user_id or "system",
                assignment_id=filters.assignment_id,
                instance_id=filters.instance_id,
                trace_id=trace_id,
                request_id=request_id,
                idempotency_key=idempotency_key,
                result="SUCCESS",
                reason="",
                before_json=None,
                after_json={"filters": filter_payload},
                ip="",
                user_agent_hash=None,
            )
        )
        estimated_records = build_audit_queryset(filters).count()
        if estimated_records > settings.COMMON_AUDIT_EXPORT_MAX_RECORDS:
            raise ApiError(AUDIT_EXPORT_TOO_LARGE)
    state["estimated_records"] = estimated_records
    save_export_state(state)
    run_audit_export.delay(operation_id)
    return state


def _audit_row(log: AuditLog) -> dict[str, Any]:
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
        "user_agent": log.user_agent_hash,
        "occurred_at": log.occurred_at.isoformat(),
        "created_at": log.created_at.isoformat(),
    }


def _mask_export_value(field: str, value: Any) -> Any:
    if field == "ip_address" and isinstance(value, str) and value:
        return value if "*" in value else mask_ip(value)
    if field == "user_agent":
        return "masked"
    return mask_sensitive(value)


def _masked_row(row: dict[str, Any], mask_fields: list[str]) -> dict[str, Any]:
    for field in mask_fields:
        if field in row:
            row[field] = _mask_export_value(field, row[field])
    return row


def _write_rows(file: Any, queryset: Any, export_format: str, mask_fields: list[str]) -> int:
    count = 0
    if export_format == "csv":
        text = io.TextIOWrapper(file, encoding="utf-8", newline="")
        try:
            writer = csv.DictWriter(text, fieldnames=EXPORT_FIELDS)
            writer.writeheader()
            for log in queryset.iterator(chunk_size=500):
                writer.writerow(_masked_row(_audit_row(log), mask_fields))
                count += 1
        finally:
            text.detach()
    else:
        file.write(b"[")
        for log in queryset.iterator(chunk_size=500):
            if count:
                file.write(b",")
            row = json.dumps(_masked_row(_audit_row(log), mask_fields), ensure_ascii=False)
            file.write(row.encode("utf-8"))
            count += 1
        file.write(b"]")
    return count


def _content_type(export_format: str) -> str:
    return "text/csv" if export_format == "csv" else "application/json"


@shared_task(name="apps.common.run_audit_export")
def run_audit_export(operation_id: str) -> None:
    state = get_export_state(operation_id)
    if state is None:
        return
    filters = AuditQueryFilters()
    try:
        filters = filters_from_payload(state["filters"])
        queryset = build_audit_queryset(filters).order_by("id")
        export_format = str(state["format"])
        mask_fields = list(state["masked_fields"])
        file_key = f"audit-exports/{operation_id}.{export_format}"
        with tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024) as file:
            total_records = _write_rows(file, queryset, export_format, mask_fields)
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
            minio_client().upload_fileobj(
                file,
                settings.MINIO.export_bucket,
                file_key,
                ExtraArgs={"ContentType": _content_type(export_format)},
            )
    except Exception as exc:  # noqa: BLE001
        state["status"] = "FAILED"
        state["error"] = str(mask_sensitive(str(exc)))
        save_export_state(state)
        record_audit(
            AuditRecord(
                actor_user_id=state.get("actor_user_id"),
                actor_role_code=state.get("actor_role_code"),
                action="audit_export.failed",
                target_type="USER",
                target_id=state.get("actor_user_id") or "system",
                assignment_id=filters.assignment_id,
                instance_id=filters.instance_id,
                trace_id=str(state["trace_id"]),
                request_id=str(state["request_id"]),
                idempotency_key=state.get("idempotency_key"),
                result="FAILURE",
                reason=str(mask_sensitive(str(exc))),
                before_json=None,
                after_json=state.get("filters"),
                ip="",
                user_agent_hash=None,
            )
        )
        return

    state.update(
        {
            "status": "COMPLETED",
            "file_key": file_key,
            "file_url": presign_download(
                settings.MINIO.export_bucket,
                file_key,
                expires_in=AUDIT_EXPORT_TTL_SECONDS,
            ),
            "file_size_bytes": file_size,
            "total_records": total_records,
        }
    )
    save_export_state(state)
    record_audit(
        AuditRecord(
            actor_user_id=state.get("actor_user_id"),
            actor_role_code=state.get("actor_role_code"),
            action="audit_export.completed",
            target_type="USER",
            target_id=state.get("actor_user_id") or "system",
            assignment_id=filters.assignment_id,
            instance_id=filters.instance_id,
            trace_id=str(state["trace_id"]),
            request_id=str(state["request_id"]),
            idempotency_key=state.get("idempotency_key"),
            result="SUCCESS",
            reason="",
            before_json=None,
            after_json={
                "file_key": file_key,
                "total_records": total_records,
                "masked_fields": mask_fields,
                "format": export_format,
            },
            ip="",
            user_agent_hash=None,
        )
    )
