from __future__ import annotations

import json
import threading
import uuid

import pytest
from django.test import Client

from .conftest import grant_permission, make_user


class FakeRedis:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, str]] = {}
        self.lock = threading.Lock()

    def eval(self, _script: str, _numkeys: int, key: str, digest: str, _ttl: int) -> int:
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

    def expire(self, _key: str, _ttl: int) -> None:
        return None


def _headers(access: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {access}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


def _post(client: Client, path: str, payload: dict[str, object], headers: dict[str, str]):
    return client.post(
        path, data=json.dumps(payload), content_type="application/json", headers=headers
    )


def test_me_returns_token_identity_and_permissions(
    roles: dict[str, object], active_membership: dict[str, str]
) -> None:
    user = make_user(roles, username="me", role_code="ORG_ADMIN")
    grant_permission(roles["ORG_ADMIN"], "identity:read")
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(user.id, "ORG_ADMIN", "ACTIVE")
    response = Client().get("/auth/me", headers=_headers(access))
    payload = response.json()["data"]

    assert response.status_code == 200
    assert payload["id"] == user.id
    assert payload["role_code"] == "ORG_ADMIN"
    assert payload["permissions"] == ["identity:read"]


def test_permission_matrix_returns_readonly_view(
    roles: dict[str, object], active_membership: dict[str, str]
) -> None:
    admin = make_user(roles, username="matrix-admin", role_code="SYSTEM_ADMIN")
    grant_permission(roles["USER"], "identity:read")
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(admin.id, "SYSTEM_ADMIN", "ACTIVE")
    response = Client().get(
        "/admin/permissions",
        {"role_code": "USER", "resource": "IDENTITY"},
        headers=_headers(access),
    )
    payload = response.json()["data"]

    assert response.status_code == 200
    assert payload["total_roles"] == 1
    assert payload["matrix"][0]["permissions"][0]["perm_code"] == "identity:read"


def test_admin_create_user_is_idempotent_and_initializes_quota(
    roles: dict[str, object],
    active_membership: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = make_user(roles, username="create-admin", role_code="SYSTEM_ADMIN")
    redis = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: redis)
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(admin.id, "SYSTEM_ADMIN", "ACTIVE")
    payload = {
        "mode": "single",
        "username": "created_user",
        "password": "Password123",
        "email": "created@example.com",
        "role_id": roles["USER"].id,
        "send_welcome": False,
    }
    key = str(uuid.uuid4())
    first = _post(Client(), "/admin/users", payload, _headers(access, key))
    second = _post(Client(), "/admin/users", payload, _headers(access, key))
    from apps.identity.models import User, UserQuota

    assert first.status_code == second.status_code == 201, (first.content, second.content)
    assert first.content == second.content
    assert User.objects.filter(username="created_user").count() == 1
    assert UserQuota.objects.filter(user__username="created_user", max_instances=5).exists()


def test_admin_disable_user_publishes_revocation_events(
    roles: dict[str, object],
    active_membership: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = make_user(roles, username="disable-admin", role_code="SYSTEM_ADMIN")
    target = make_user(roles, username="disable-target", role_code="USER")
    redis = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: redis)
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(admin.id, "SYSTEM_ADMIN", "ACTIVE")
    response = Client().patch(
        f"/admin/users/{target.id}",
        data=json.dumps({"status": "DISABLED"}),
        content_type="application/json",
        headers=_headers(access, str(uuid.uuid4())),
    )
    from apps.common.models import OutboxEvent

    target.refresh_from_db()
    topics = set(OutboxEvent.objects.values_list("topic", flat=True))
    assert response.status_code == 200
    assert target.status == "DISABLED"
    assert {"workspace.session.revoked", "notification.revoked"}.issubset(topics)


def test_quota_api_uses_contract_aliases_and_updates_limit(
    roles: dict[str, object],
    active_membership: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = make_user(roles, username="quota-admin", role_code="SYSTEM_ADMIN")
    target = make_user(roles, username="quota-target", role_code="USER")
    redis = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: redis)
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(admin.id, "SYSTEM_ADMIN", "ACTIVE")
    before = (
        Client().get(f"/admin/user-quotas/{target.id}", headers=_headers(access)).json()["data"]
    )
    response = Client().patch(
        f"/admin/user-quotas/{target.id}",
        data=json.dumps({"max_instances": 8}),
        content_type="application/json",
        headers=_headers(access, str(uuid.uuid4())),
    )
    after = response.json()["data"]

    assert response.status_code == 200
    assert before["max_concurrent_instances"] == 5
    assert after["max_concurrent_instances"] == 8
    assert "max_instances" not in after


def test_refresh_api_rotates_token(
    roles: dict[str, object], active_membership: dict[str, str]
) -> None:
    user = make_user(roles, username="refresh-api")
    from apps.identity.services.auth import issue_access_token, issue_refresh_token

    _, jti = issue_access_token(user.id, "USER", "ACTIVE")
    refresh_token = issue_refresh_token(user.id, jti)
    response = _post(Client(), "/auth/refresh", {"refresh_token": refresh_token}, {})
    payload = response.json()["data"]

    assert response.status_code == 200
    assert payload["access_token"]
    assert payload["refresh_token"] != refresh_token


def test_logout_replays_success_for_same_key(
    roles: dict[str, object],
    active_membership: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(roles, username="logout")
    redis = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: redis)
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(user.id, "USER", "ACTIVE")
    key = str(uuid.uuid4())
    headers = _headers(access, key) | {"X-Request-ID": "logout-request-id"}
    first = _post(Client(), "/auth/logout", {}, headers)
    second = _post(Client(), "/auth/logout", {}, headers)

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
