from __future__ import annotations

import uuid

import pytest
from django.test import Client

from apps.common.models import OutboxEvent

from .conftest import make_membership, make_user
from .test_me_api import FakeRedis, _headers, _post


def test_teaching_members_mask_sensitive_fields(team_settings, roles: dict[str, object]) -> None:
    admin = make_user(roles, username="admin", role_code="ORG_ADMIN")
    member = make_user(roles, username="member")
    make_membership(user_id=member.id, status="ACTIVE")
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(admin.id, "ORG_ADMIN", "ACTIVE")
    response = Client().get(
        "/api/v1/teaching/team-members",
        {"status": "ACTIVE", "keyword": "member"},
        headers=_headers(access),
    )
    payload = response.json()["data"]

    assert response.status_code == 200
    assert payload["total"] == 1
    assert payload["items"][0]["username"] == "member"
    assert "***" in payload["items"][0]["email"]
    assert "****" in payload["items"][0]["phone"]
    assert payload["summary"]["active_count"] == 1


def test_org_sub_admin_has_empty_scope_under_c8(team_settings, roles: dict[str, object]) -> None:
    sub_admin = make_user(roles, username="sub", role_code="ORG_SUB_ADMIN")
    member = make_user(roles, username="member")
    make_membership(user_id=member.id, status="ACTIVE")
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(sub_admin.id, "ORG_SUB_ADMIN", "ACTIVE")

    response = Client().get("/api/v1/teaching/team-members", headers=_headers(access))
    payload = response.json()["data"]

    assert response.status_code == 200
    assert payload["total"] == 0
    assert payload["items"] == []


def test_review_application_is_idempotent(
    team_settings,
    roles: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = make_user(roles, username="admin", role_code="ORG_ADMIN")
    applicant = make_user(roles, username="applicant")
    membership = make_membership(user_id=applicant.id, status="PENDING")
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(admin.id, "ORG_ADMIN", "ACTIVE")
    redis = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: redis)
    client = Client()
    key = str(uuid.uuid4())
    payload = {"action": "APPROVE"}

    first = _post(
        client,
        f"/api/v1/teaching/team-membership-applications/{membership.id}/review",
        payload,
        _headers(access, key),
    )
    second = _post(
        client,
        f"/api/v1/teaching/team-membership-applications/{membership.id}/review",
        payload,
        _headers(access, key),
    )

    assert first.status_code == 200
    assert second.content == first.content
    assert first.json()["data"]["status"] == "ACTIVE"
    assert OutboxEvent.objects.filter(event_type="membership.approved").count() == 1


def test_org_sub_admin_cannot_review_under_c8(
    team_settings, roles: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    sub_admin = make_user(roles, username="sub", role_code="ORG_SUB_ADMIN")
    applicant = make_user(roles, username="applicant")
    membership = make_membership(user_id=applicant.id, status="PENDING")
    from apps.identity.services.auth import issue_access_token

    monkeypatch.setattr(
        "apps.common.idempotency.redis_client",
        lambda: FakeRedis(),
    )

    access, _ = issue_access_token(sub_admin.id, "ORG_SUB_ADMIN", "ACTIVE")

    response = _post(
        Client(raise_request_exceptions=False),
        f"/api/v1/teaching/team-membership-applications/{membership.id}/review",
        {"action": "APPROVE"},
        _headers(access, str(uuid.uuid4())),
    )

    assert response.status_code == 403
    assert response.json()["code"] == 40301
