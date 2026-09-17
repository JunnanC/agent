from __future__ import annotations

import json
import threading
import uuid

import pytest
from django.test import Client, override_settings

from apps.common.audit import AuditRecord, hash_user_agent, record_audit
from apps.common.errors import (
    AUDIT_EXPORT_TOO_LARGE,
    EMPTY_FILTER,
    FORBIDDEN,
    INTERNAL_ERROR,
    RESOURCE_NOT_FOUND,
)


class FakeRedis:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, str]] = {}
        self.values: dict[str, tuple[str, int | None]] = {}
        self.lock = threading.Lock()

    def eval(self, script: str, numkeys: int, key: str, digest: str, ttl: int) -> int:
        with self.lock:
            record = self.records.get(key)
            if record is None:
                self.records[key] = {"request_digest": digest, "state": "PENDING"}
                return 1
            if record["request_digest"] != digest:
                return -1
            return 2 if record["state"] == "COMPLETED" else 0

    def hgetall(self, key: str) -> dict[str, str]:
        with self.lock:
            return dict(self.records.get(key, {}))

    def hset(self, key: str, mapping: dict[str, str]) -> None:
        with self.lock:
            self.records.setdefault(key, {}).update(mapping)

    def expire(self, key: str, ttl: int) -> None:
        return None

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        with self.lock:
            self.values[key] = (value, ex)

    def get(self, key: str) -> str | None:
        with self.lock:
            return self.values.get(key, (None, None))[0]


def _audit(
    *,
    action: str = "record.updated",
    target_id: str = "target-id",
    request_id: str = "request-id",
) -> AuditRecord:
    return AuditRecord(
        actor_user_id="1",
        actor_role_code="SYSTEM_ADMIN",
        action=action,
        target_type="USER",
        target_id=target_id,
        assignment_id=None,
        instance_id=None,
        trace_id="trace-id",
        request_id=request_id,
        idempotency_key=None,
        result="SUCCESS",
        reason="",
        before_json=None,
        after_json=None,
        ip="192.168.1.10",
        user_agent_hash=hash_user_agent("Mozilla/5.0"),
    )


def _patch_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.common.health.check_mysql", lambda: "up")
    monkeypatch.setattr("apps.common.health.check_redis", lambda: "up")
    monkeypatch.setattr("apps.common.health.minio_health", lambda: "up")


def test_health_endpoint_and_generated_request_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_health(monkeypatch)

    response = Client().get("/admin/health")
    payload = json.loads(response.content)
    request_id = response.headers["X-Request-ID"]

    assert response.status_code == 200
    assert payload["code"] == 0
    assert payload["data"]["ok"] is True
    assert payload["request_id"] == request_id
    uuid.UUID(request_id)


def test_request_id_is_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_health(monkeypatch)

    response = Client().get("/admin/health", headers={"X-Request-ID": "request-id"})
    payload = json.loads(response.content)

    assert response.headers["X-Request-ID"] == "request-id"
    assert payload["request_id"] == "request-id"


@override_settings(COMMON_AUDITABLE_ACTOR_PROVIDER="apps.common.tests.providers.UserActorProvider")
def test_non_system_admin_receives_numeric_forbidden(common_tables: None) -> None:
    response = Client(raise_request_exception=False).get("/admin/audit-logs")
    payload = json.loads(response.content)

    assert response.status_code == FORBIDDEN.http_status
    assert payload["code"] == FORBIDDEN.code
    assert "<html" not in response.content.decode().lower()


@override_settings(
    COMMON_AUDITABLE_ACTOR_PROVIDER="apps.common.tests.providers.SystemAdminActorProvider"
)
def test_audit_list_filters_and_paginates(common_tables: None) -> None:
    record_audit(_audit(target_id="first"))
    record_audit(_audit(target_id="second"))
    record_audit(_audit(action="record.deleted", target_id="other"))

    response = Client().get(
        "/admin/audit-logs",
        {"action": "record.updated", "resource_type": "USER", "page": "2", "page_size": "1"},
        headers={"X-Request-ID": "request-id"},
    )
    payload = json.loads(response.content)
    data = payload["data"]

    assert response.status_code == 200
    assert payload["code"] == 0
    assert data["page"] == 2
    assert data["page_size"] == 1
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["items"][0]["target_id"] == "first"
    assert payload["request_id"] == "request-id"


@override_settings(
    COMMON_AUDITABLE_ACTOR_PROVIDER="apps.common.tests.providers.SystemAdminActorProvider"
)
def test_audit_export_returns_accepted_and_status(
    common_tables: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    redis = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: redis)
    monkeypatch.setattr("apps.common.audit_export.redis_client", lambda: redis)
    monkeypatch.setattr(
        "apps.common.audit_export.run_audit_export.delay", lambda operation_id: None
    )
    key = str(uuid.uuid4())
    body = json.dumps({"filters": {"user_id": "1"}, "format": "csv"})

    response = Client().post(
        "/admin/audit-logs/export",
        data=body,
        content_type="application/json",
        headers={"X-Request-ID": "request-id", "Idempotency-Key": key},
    )
    payload = json.loads(response.content)
    operation_id = payload["data"]["operation_id"]

    assert response.status_code == 202
    assert payload["code"] == 0
    assert payload["data"]["status"] == "ACCEPTED"
    assert payload["data"]["trace_id"]
    assert payload["data"]["estimated_records"] == 1

    status_response = Client().get(
        f"/admin/audit-logs/export/{operation_id}",
        headers={"X-Request-ID": "request-id"},
    )
    status_payload = json.loads(status_response.content)

    assert status_response.status_code == 200
    assert status_payload["data"]["operation_id"] == operation_id
    assert status_payload["data"]["status"] == "ACCEPTED"


@override_settings(
    COMMON_AUDITABLE_ACTOR_PROVIDER="apps.common.tests.providers.SystemAdminActorProvider"
)
def test_audit_export_replays_same_response(
    common_tables: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    redis = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: redis)
    monkeypatch.setattr("apps.common.audit_export.redis_client", lambda: redis)
    delay_calls: list[str] = []
    monkeypatch.setattr("apps.common.audit_export.run_audit_export.delay", delay_calls.append)
    key = str(uuid.uuid4())
    body = json.dumps({"filters": {"user_id": "1"}, "format": "json"})
    client = Client(raise_request_exception=False)
    headers = {"X-Request-ID": "request-id", "Idempotency-Key": key}

    first = client.post(
        "/admin/audit-logs/export", body, content_type="application/json", headers=headers
    )
    second = client.post(
        "/admin/audit-logs/export", body, content_type="application/json", headers=headers
    )

    assert first.status_code == second.status_code == 202
    assert first.content == second.content
    assert len(delay_calls) == 1


@override_settings(
    COMMON_AUDITABLE_ACTOR_PROVIDER="apps.common.tests.providers.SystemAdminActorProvider"
)
def test_audit_export_requires_filter(common_tables: None, monkeypatch: pytest.MonkeyPatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: redis)

    response = Client().post(
        "/admin/audit-logs/export",
        data=json.dumps({"filters": {}}),
        content_type="application/json",
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    payload = json.loads(response.content)

    assert response.status_code == EMPTY_FILTER.http_status
    assert payload["code"] == EMPTY_FILTER.code


@override_settings(
    COMMON_AUDITABLE_ACTOR_PROVIDER="apps.common.tests.providers.SystemAdminActorProvider",
    COMMON_AUDIT_EXPORT_MAX_RECORDS=0,
)
def test_audit_export_rejects_too_many_records(
    common_tables: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    record_audit(_audit())
    redis = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: redis)
    monkeypatch.setattr("apps.common.audit_export.redis_client", lambda: redis)

    response = Client().post(
        "/admin/audit-logs/export",
        data=json.dumps({"filters": {"user_id": "1"}}),
        content_type="application/json",
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    payload = json.loads(response.content)

    assert response.status_code == AUDIT_EXPORT_TOO_LARGE.http_status
    assert payload["code"] == AUDIT_EXPORT_TOO_LARGE.code


@override_settings(
    COMMON_AUDITABLE_ACTOR_PROVIDER="apps.common.tests.providers.SystemAdminActorProvider"
)
def test_audit_export_status_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr("apps.common.audit_export.redis_client", lambda: redis)

    response = Client(raise_request_exception=False).get("/admin/audit-logs/export/missing")
    payload = json.loads(response.content)

    assert response.status_code == RESOURCE_NOT_FOUND.http_status
    assert payload["code"] == RESOURCE_NOT_FOUND.code


def test_unexpected_error_returns_json_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.common.health.check_mysql", lambda: 1 / 0)

    response = Client(raise_request_exception=False).get("/admin/health")
    payload = json.loads(response.content)
    content = response.content.decode()

    assert response.status_code == INTERNAL_ERROR.http_status
    assert payload["code"] == INTERNAL_ERROR.code
    assert response.headers["Content-Type"].startswith("application/json")
    assert "Traceback" not in content
    assert "<html" not in content.lower()
