from __future__ import annotations

import json
import uuid

import pytest
from django.test import Client

from apps.common.models import AuditLog

from .conftest import make_membership, make_user
from .test_me_api import FakeRedis, _headers


def test_user_cannot_view_other_membership(team_settings, roles: dict[str, object]) -> None:
    user = make_user(roles, username="current")
    other = make_user(roles, username="other")
    make_membership(user_id=other.id, status="ACTIVE")
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(user.id, "USER", None)

    response = Client().get(
        "/api/v1/me/team-membership",
        {"user_id": str(other.id), "team_id": "1"},
        headers=_headers(access),
    )
    payload = response.json()["data"]

    assert response.status_code == 200
    assert payload["total"] == 0
    assert payload["items"] == []


def test_write_audit_is_masked_and_traceable(
    team_settings,
    roles: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(roles, username="user")
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(user.id, "USER", None)
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: FakeRedis())

    response = Client().post(
        "/api/v1/me/team-membership/applications",
        data=json.dumps({"team_id": 1, "message": "申请加入"}),
        content_type="application/json",
        headers=_headers(access, str(uuid.uuid4()))
        | {"X-Request-ID": "request-id", "X-Trace-ID": "trace-id"},
    )

    assert response.status_code == 201
    assert response.headers["X-Request-ID"] == "request-id"
    assert response.headers["X-Trace-ID"] == "trace-id"
    assert AuditLog.objects.filter(
        action="membership.apply", request_id="request-id", trace_id="trace-id"
    ).exists()
