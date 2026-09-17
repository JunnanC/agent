from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apps.common.audit import (
    AuditQueryFilters,
    AuditRecord,
    build_audit_queryset,
    hash_user_agent,
    mask_ip,
    record_audit,
)
from apps.common.models import AuditLog


def _record(
    *,
    result: str = "SUCCESS",
    target_type: str = "USER",
    target_id: str = "target-id",
    assignment_id: str | None = None,
    instance_id: str | None = None,
    created_at: datetime | None = None,
) -> AuditRecord:
    return AuditRecord(
        actor_user_id="1",
        actor_role_code="SYSTEM_ADMIN",
        action="record.updated",
        target_type=target_type,
        target_id=target_id,
        assignment_id=assignment_id,
        instance_id=instance_id,
        trace_id="trace-id",
        request_id="request-id",
        idempotency_key="idempotency-key",
        result=result,  # type: ignore[arg-type]
        reason="password=secret",
        before_json={"password": "secret"},
        after_json={"token": "secret"},
        ip="192.168.1.10",
        user_agent_hash=hash_user_agent("Mozilla/5.0"),
    )


def test_audit_model_is_unmanaged() -> None:
    assert AuditLog._meta.managed is False
    assert AuditLog._meta.db_table == "audit_logs"


def test_mask_ip() -> None:
    assert mask_ip("192.168.1.10") == "192.168.*.*"
    assert mask_ip("2001:db8::1") == "2001:db8::*"
    assert mask_ip("invalid") == "invalid"
    assert mask_ip("") == ""


def test_record_audit_masks_sensitive_values(common_tables: None) -> None:
    log = record_audit(_record())

    assert log.actor_user_id == "1"
    assert log.actor_role_code == "SYSTEM_ADMIN"
    assert log.result == "SUCCESS"
    assert log.reason == "password=***"
    assert log.before_json == {"password": "***"}
    assert log.after_json == {"token": "***"}
    assert log.ip == "192.168.*.*"
    assert log.user_agent_hash == hash_user_agent("Mozilla/5.0")
    assert "Mozilla" not in (log.user_agent_hash or "")
    assert log.trace_id == "trace-id"
    assert log.request_id == "request-id"


def test_record_audit_supports_denied_and_failure(common_tables: None) -> None:
    denied = record_audit(_record(result="DENIED"))
    failure = record_audit(_record(result="FAILURE"))

    assert denied.result == "DENIED"
    assert failure.result == "FAILURE"


def test_build_audit_queryset_filters(common_tables: None) -> None:
    now = datetime.now(UTC)
    old = record_audit(_record(target_id="old"))
    old.created_at = now - timedelta(days=2)
    old.save(update_fields=["created_at"])
    current = record_audit(_record(target_id="current"))
    record_audit(_record(target_id="unrelated"))

    queryset = build_audit_queryset(
        AuditQueryFilters(
            user_id="1",
            action="record.updated",
            resource_type="USER",
            resource_id="current",
            request_id="request-id",
            trace_id="trace-id",
            created_after=now - timedelta(minutes=1),
            created_before=now + timedelta(minutes=1),
        )
    )

    assert list(queryset) == [current]


def test_build_audit_queryset_related_ids(common_tables: None) -> None:
    direct = record_audit(_record(target_id="related-id"))
    assignment_associated = record_audit(_record(target_id="other", assignment_id="related-id"))
    instance_associated = record_audit(_record(target_id="another", instance_id="related-id"))
    record_audit(_record(target_id="unrelated"))

    by_assignment = build_audit_queryset(AuditQueryFilters(assignment_id="related-id"))
    by_instance = build_audit_queryset(AuditQueryFilters(instance_id="related-id"))

    assert set(by_assignment) == {direct, assignment_associated}
    assert set(by_instance) == {direct, instance_associated}
