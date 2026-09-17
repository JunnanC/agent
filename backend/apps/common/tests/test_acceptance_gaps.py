from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from apps.common.audit import AuditQueryFilters, AuditRecord, record_audit
from apps.common.audit_export import create_audit_export, run_audit_export
from apps.common.context import RequestContext, current_context, reset_context, set_context
from apps.common.errors import ERROR_CODES
from apps.common.middleware import RequestTraceMiddleware
from apps.common.models import AuditLog, OutboxEvent
from apps.common.outbox import dispatch_due_outbox


def test_outbox_model_has_exact_frozen_fields() -> None:
    fields = [field.name for field in OutboxEvent._meta.concrete_fields]

    assert fields == [
        "id",
        "event_id",
        "event_type",
        "aggregate_type",
        "aggregate_id",
        "assignment_id",
        "instance_id",
        "topic",
        "payload_json",
        "status",
        "attempt_count",
        "available_at",
        "published_at",
        "last_error",
        "trace_id",
        "created_at",
    ]


def test_audit_model_has_exact_frozen_fields() -> None:
    fields = [field.name for field in AuditLog._meta.concrete_fields]

    assert fields == [
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
        "ip",
        "user_agent_hash",
        "occurred_at",
        "created_at",
    ]


def test_error_dictionary_has_exact_symbol_set() -> None:
    assert set(ERROR_CODES) == {
        "VALIDATION_ERROR",
        "EMPTY_FILTER",
        "UNAUTHENTICATED",
        "TOKEN_EXPIRED",
        "REFRESH_TOKEN_REVOKED",
        "FORBIDDEN",
        "ACCOUNT_DISABLED",
        "MEMBERSHIP_REQUIRED",
        "MEMBERSHIP_PENDING",
        "MEMBERSHIP_INACTIVE",
        "RESOURCE_NOT_FOUND",
        "STATE_CONFLICT",
        "IDEMPOTENCY_CONFLICT",
        "REVISION_CONFLICT",
        "MEMBERSHIP_CHANGE_BLOCKED",
        "LAST_TEAM_ADMIN_PROTECTED",
        "FILE_TOO_LARGE",
        "POLICY_REJECTED",
        "QUOTA_EXCEEDED",
        "PRECHECK_FAILED",
        "FILE_SCAN_FAILED",
        "AUDIT_EXPORT_TOO_LARGE",
        "RATE_LIMITED",
        "FILE_UPLOAD_LIMITED",
        "INTERNAL_ERROR",
        "RUNTIME_UNAVAILABLE",
        "DEPENDENCY_UNAVAILABLE",
        "AGENT_TOOL_REJECTED",
        "WORKSPACE_ACCESS_DENIED",
        "TEMPLATE_VERSION_NOT_PUBLISHED",
        "REVIEW_ALREADY_EXISTS",
        "REPORT_ALREADY_SUBMITTED",
        "ARCHIVE_NOT_COMPLETED",
        "ASSIGNMENT_NOT_ACTIVE",
        "TIME_WINDOW_INVALID",
        "TEMPLATE_NOT_PUBLISHED",
        "USER_NOT_ACTIVE_MEMBER",
        "CANNOT_WITHDRAW_STATUS",
    }


def test_audit_supports_system_actor_and_utc_timestamps(common_tables: None) -> None:
    log = record_audit(
        AuditRecord(
            actor_user_id=None,
            actor_role_code=None,
            action="system.action",
            target_type="COMPENSATION",
            target_id="system",
            assignment_id=None,
            instance_id=None,
            trace_id="trace-id",
            request_id="request-id",
            idempotency_key=None,
            result="SUCCESS",
            reason="",
            before_json=None,
            after_json=None,
            ip="",
            user_agent_hash=None,
        )
    )

    assert log.actor_user_id is None
    assert log.occurred_at.utcoffset().total_seconds() == 0
    assert log.created_at.utcoffset().total_seconds() == 0


def test_async_middleware_cleans_context_after_response() -> None:
    def view(request: HttpRequest) -> HttpResponse:
        return HttpResponse("ok")

    middleware = RequestTraceMiddleware(view)
    request = RequestFactory().get("/health/", HTTP_X_REQUEST_ID="request-id")

    response = asyncio.run(middleware.__acall__(request))

    assert response.status_code == 200
    assert response["X-Request-ID"] == "request-id"
    with pytest.raises(RuntimeError):
        current_context()


class RecordingTransport:
    def __init__(self) -> None:
        self.event_ids: list[str] = []

    def publish(self, topic: str, event_id: str, payload_json: str) -> None:
        self.event_ids.append(event_id)


def test_outbox_event_is_not_dispatched_twice(common_tables: None) -> None:
    now = datetime.now(UTC)
    OutboxEvent.objects.create(
        event_id="event-id",
        event_type="generic.updated",
        aggregate_type="SESSION",
        aggregate_id="aggregate-id",
        assignment_id=None,
        instance_id=None,
        topic="generic-events",
        payload_json={},
        status="PENDING",
        attempt_count=0,
        available_at=now,
        published_at=None,
        last_error="",
        trace_id="trace-id",
        created_at=now,
    )
    transport = RecordingTransport()

    assert dispatch_due_outbox(transport=transport) == 1
    assert dispatch_due_outbox(transport=transport) == 0
    assert transport.event_ids == ["event-id"]


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = value

    def get(self, key: str) -> str | None:
        return self.values.get(key)


class FakeMinio:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, bytes]] = []

    def upload_fileobj(self, file: Any, bucket: str, key: str, **kwargs: Any) -> None:
        self.uploads.append((bucket, key, file.read()))


def test_audit_export_supports_custom_mask_fields(
    common_tables: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    record_audit(
        AuditRecord(
            actor_user_id="1",
            actor_role_code="SYSTEM_ADMIN",
            action="record.updated",
            target_type="USER",
            target_id="target-id",
            assignment_id=None,
            instance_id=None,
            trace_id="trace-id",
            request_id="request-id",
            idempotency_key=None,
            result="SUCCESS",
            reason="password=secret",
            before_json=None,
            after_json=None,
            ip="10.20.30.40",
            user_agent_hash=None,
        )
    )
    redis = FakeRedis()
    minio = FakeMinio()
    monkeypatch.setattr("apps.common.audit_export.redis_client", lambda: redis)
    monkeypatch.setattr("apps.common.audit_export.minio_client", lambda: minio)
    monkeypatch.setattr("apps.common.audit_export.presign_download", lambda *args, **kwargs: "url")
    monkeypatch.setattr(
        "apps.common.audit_export.run_audit_export.delay", lambda operation_id: None
    )
    token = set_context(RequestContext("request-id", "trace-id", "1", "test"))
    try:
        state = create_audit_export(
            filters=AuditQueryFilters(user_id="1"),
            export_format="json",
            mask_fields=["reason", "ip_address"],
            actor_user_id="1",
            actor_role_code="SYSTEM_ADMIN",
            idempotency_key="idempotency-key",
            request_id="request-id",
        )
    finally:
        reset_context(token)

    run_audit_export(str(state["operation_id"]))
    rows = json.loads(minio.uploads[0][2])

    assert state["estimated_records"] == 2
    assert rows[0]["reason"] == "password=***"
    assert rows[0]["ip_address"] == "10.20.*.*"
