from __future__ import annotations

import json
import threading
import uuid

import pytest
from django.test import Client

from apps.common.models import OutboxEvent

from .conftest import make_membership, make_user


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


def test_my_membership_returns_only_current_user(team_settings, roles: dict[str, object]) -> None:
    user = make_user(roles, username="current")
    other = make_user(roles, username="other")
    make_membership(user_id=user.id, status="ACTIVE")
    make_membership(user_id=other.id, status="PENDING")
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(user.id, "USER", "ACTIVE")

    response = Client().get("/api/v1/me/team-membership", headers=_headers(access))
    payload = response.json()["data"]

    assert response.status_code == 200
    assert payload["total"] == 1
    assert payload["items"][0]["membership_id"] == user.id
    assert payload["items"][0]["status"] == "ACTIVE"
    assert payload["blocking_summary"] == {
        "has_active_membership": True,
        "has_pending_application": False,
        "can_apply": False,
        "block_reason": "ACTIVE",
    }


def test_application_is_idempotent_and_publishes_event(
    team_settings,
    roles: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(roles, username="applicant")
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(user.id, "USER", None)
    redis = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: redis)
    client = Client()
    key = str(uuid.uuid4())
    payload = {"team_id": 1, "message": "申请加入"}

    first = _post(client, "/api/v1/me/team-membership/applications", payload, _headers(access, key))
    second = _post(
        client, "/api/v1/me/team-membership/applications", payload, _headers(access, key)
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.content == second.content
    assert first.json()["data"]["status"] == "PENDING"
    assert OutboxEvent.objects.filter(event_type="membership.applied").count() == 1


def test_non_user_cannot_apply(
    team_settings, roles: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = make_user(roles, username="admin", role_code="ORG_ADMIN")
    from apps.identity.services.auth import issue_access_token

    monkeypatch.setattr(
        "apps.common.idempotency.redis_client",
        lambda: FakeRedis(),
    )

    access, _ = issue_access_token(admin.id, "ORG_ADMIN", "ACTIVE")

    response = _post(
        Client(raise_request_exceptions=False),
        "/api/v1/me/team-membership/applications",
        {"team_id": 1},
        _headers(access, str(uuid.uuid4())),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == 40301
