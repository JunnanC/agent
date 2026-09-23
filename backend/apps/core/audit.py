from __future__ import annotations

import hashlib
import ipaddress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from django.db.models import Q, QuerySet

from .masking import mask_sensitive
from .models import AuditLog


@dataclass(frozen=True)
class AuditRecord:
    actor_user_id: str | None
    actor_role_code: str | None
    action: str
    target_type: str
    target_id: str
    assignment_id: str | None
    instance_id: str | None
    trace_id: str
    request_id: str
    idempotency_key: str | None
    result: Literal["SUCCESS", "DENIED", "FAILURE"]
    reason: str
    before_json: Any
    after_json: Any
    ip: str
    user_agent_hash: str | None


@dataclass(frozen=True)
class AuditQueryFilters:
    user_id: str | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    assignment_id: str | None = None
    instance_id: str | None = None
    ip_address: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


def mask_ip(value: str) -> str:
    if not value:
        return ""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return "invalid"
    if address.version == 4:
        parts = value.split(".")
        return f"{parts[0]}.{parts[1]}.*.*"
    parts = value.split(":")
    return ":".join(parts[:2]) + "::*"


def hash_user_agent(value: str) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def record_audit(record: AuditRecord) -> AuditLog:
    now = datetime.now(UTC)
    return AuditLog.objects.create(
        actor_user_id=record.actor_user_id,
        actor_role_code=record.actor_role_code,
        action=record.action,
        target_type=record.target_type,
        target_id=record.target_id,
        assignment_id=record.assignment_id,
        instance_id=record.instance_id,
        trace_id=record.trace_id,
        request_id=record.request_id,
        idempotency_key=record.idempotency_key,
        result=record.result,
        reason=str(mask_sensitive(record.reason)),
        before_json=mask_sensitive(record.before_json),
        after_json=mask_sensitive(record.after_json),
        ip=mask_ip(record.ip),
        user_agent_hash=record.user_agent_hash,
        occurred_at=now,
        created_at=now,
    )


def build_audit_queryset(filters: AuditQueryFilters) -> QuerySet[AuditLog]:
    queryset = AuditLog.objects.all()
    if filters.user_id:
        queryset = queryset.filter(actor_user_id=filters.user_id)
    if filters.action:
        queryset = queryset.filter(action=filters.action)
    if filters.resource_type:
        queryset = queryset.filter(target_type=filters.resource_type)
    if filters.resource_id:
        queryset = queryset.filter(target_id=filters.resource_id)
    if filters.request_id:
        queryset = queryset.filter(request_id=filters.request_id)
    if filters.trace_id:
        queryset = queryset.filter(trace_id=filters.trace_id)
    if filters.assignment_id:
        queryset = queryset.filter(
            Q(assignment_id=filters.assignment_id) | Q(target_id=filters.assignment_id)
        )
    if filters.instance_id:
        queryset = queryset.filter(
            Q(instance_id=filters.instance_id) | Q(target_id=filters.instance_id)
        )
    if filters.ip_address:
        queryset = queryset.filter(ip=filters.ip_address)
    if filters.created_after:
        queryset = queryset.filter(created_at__gte=filters.created_after)
    if filters.created_before:
        queryset = queryset.filter(created_at__lte=filters.created_before)
    return queryset
