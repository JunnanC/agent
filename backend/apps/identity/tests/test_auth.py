from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.common.errors import UNAUTHENTICATED

from .conftest import make_user


def test_login_success_and_wrong_password_do_not_reveal_account(
    roles: dict[str, object], active_membership: dict[str, str]
) -> None:
    make_user(roles, username="known", password="Password123")
    client = Client()

    success = client.post(
        "/auth/login",
        data=json.dumps({"username": "known", "password": "Password123"}),
        content_type="application/json",
    )
    failure = client.post(
        "/auth/login",
        data=json.dumps({"username": "missing", "password": "Password123"}),
        content_type="application/json",
    )
    wrong_password = client.post(
        "/auth/login",
        data=json.dumps({"username": "known", "password": "WrongPass123"}),
        content_type="application/json",
    )

    assert success.status_code == 200, success.content
    assert success.json()["data"]["access_token"]
    assert success.json()["data"]["user"]["membership_status"] == "ACTIVE"
    assert failure.status_code == wrong_password.status_code == UNAUTHENTICATED.http_status
    assert failure.json()["message"] == wrong_password.json()["message"]


def test_refresh_rotates_token_and_replay_revokes_sessions(
    roles: dict[str, object], active_membership: dict[str, str]
) -> None:
    from django.core.cache import cache

    user = make_user(roles, username="known")
    from apps.identity.services.auth import issue_access_token, issue_refresh_token, refresh

    _, jti = issue_access_token(user.id, "USER", "ACTIVE")
    old_refresh = issue_refresh_token(user.id, jti)
    rotated = refresh(old_refresh)

    assert rotated["refresh_token"] != old_refresh
    from apps.common.errors import ApiError

    with pytest.raises(ApiError):
        refresh(old_refresh)
    sessions = cache.get(f"identity:sessions:{user.id}")
    assert sessions is None or sessions == []
