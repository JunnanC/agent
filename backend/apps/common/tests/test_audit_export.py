from __future__ import annotations

import csv
import io
import json
from datetime import datetime

import pytest

from apps.common.audit import AuditQueryFilters, AuditRecord, hash_user_agent, record_audit
from apps.common.audit_export import create_audit_export, run_audit_export
from apps.common.context import RequestContext, reset_context, set_context
from apps.common.models import AuditLog


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = value

    def get(self, key: str) -> str | None:
        return self.values.get(key)


class FakeMinio:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, bytes, dict[str, str]]] = []

    def upload_fileobj(self, file: io.BufferedIOBase, bucket: str, key: str, **kwargs: str) -> None:
        self.uploads.append((bucket, key, file.read(), dict(kwargs)))


def _record() -> AuditRecord:
    return AuditRecord(
        actor_user_id="1",
        actor_role_code="SYSTEM_ADMIN",
        action="record.updated",
        target_type="USER",
        target_id="target-id",
        assignment_id=None,
        instance_id=None,
        trace_id="trace-id",
        request_id="request-id",
        idempotency_key="idempotency-key",
        result="SUCCESS",
        reason="password=secret",
        before_json={"password": "secret"},
        after_json={"token": "secret"},
        ip="10.20.30.40",
        user_agent_hash=hash_user_agent("Mozilla/5.0"),
    )


def _create_state(monkeypatch: pytest.MonkeyPatch, export_format: str) -> str:
    token = set_context(RequestContext("request-id", "trace-id", "1", "test"))
    try:
        state = create_audit_export(
            filters=AuditQueryFilters(user_id="1"),
            export_format=export_format,
            mask_fields=["ip_address", "user_agent"],
            actor_user_id="1",
            actor_role_code="SYSTEM_ADMIN",
            idempotency_key="idempotency-key",
            request_id="request-id",
        )
    finally:
        reset_context(token)
    return str(state["operation_id"])


@pytest.mark.parametrize("export_format", ["csv", "json"])
def test_run_audit_export_generates_masked_file(
    common_tables: None, monkeypatch: pytest.MonkeyPatch, export_format: str
) -> None:
    record_audit(_record())
    redis = FakeRedis()
    minio = FakeMinio()
    monkeypatch.setattr("apps.common.audit_export.redis_client", lambda: redis)
    monkeypatch.setattr("apps.common.audit_export.minio_client", lambda: minio)
    monkeypatch.setattr("apps.common.audit_export.presign_download", lambda *args, **kwargs: "url")
    monkeypatch.setattr(
        "apps.common.audit_export.run_audit_export.delay", lambda operation_id: None
    )
    operation_id = _create_state(monkeypatch, export_format)

    run_audit_export(operation_id)

    bucket, key, content, extra_args = minio.uploads[0]
    assert bucket == "export"
    assert key == f"audit-exports/{operation_id}.{export_format}"
    assert extra_args["ExtraArgs"]["ContentType"] == (
        "text/csv" if export_format == "csv" else "application/json"
    )

    if export_format == "csv":
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))
    else:
        rows = json.loads(content)

    assert len(rows) == 2
    assert rows[0]["ip_address"] == "10.20.*.*"
    assert rows[0]["user_agent"] == "masked"
    assert "secret" not in content.decode("utf-8").lower()

    state = json.loads(redis.values[f"audit-export:{operation_id}"])
    accepted_at = datetime.fromisoformat(state["accepted_at"])
    expires_at = datetime.fromisoformat(state["expires_at"])
    assert (expires_at - accepted_at).total_seconds() == 24 * 60 * 60
    assert state["status"] == "COMPLETED"
    assert state["total_records"] == 2
    assert state["file_size_bytes"] == len(content)
    assert state["file_url"] == "url"

    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"record.updated", "audit_export.requested", "audit_export.completed"} <= actions


def test_run_audit_export_records_failure(
    common_tables: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    record_audit(_record())
    redis = FakeRedis()
    monkeypatch.setattr("apps.common.audit_export.redis_client", lambda: redis)
    monkeypatch.setattr(
        "apps.common.audit_export.minio_client",
        lambda: (_ for _ in ()).throw(RuntimeError("secret-token")),
    )
    monkeypatch.setattr(
        "apps.common.audit_export.run_audit_export.delay", lambda operation_id: None
    )
    operation_id = _create_state(monkeypatch, "csv")

    run_audit_export(operation_id)

    state = json.loads(redis.values[f"audit-export:{operation_id}"])
    assert state["status"] == "FAILED"
    assert "secret" not in state["error"].lower()
    assert AuditLog.objects.filter(action="audit_export.failed", result="FAILURE").exists()
