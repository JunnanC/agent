from __future__ import annotations

import threading

import pytest
from django.db import OperationalError

from apps.common.errors import MEMBERSHIP_CHANGE_BLOCKED, STATE_CONFLICT, ApiError
from apps.membership.services import apply_membership, review_application

from .conftest import make_membership, make_user


def test_duplicate_pending_application_is_blocked(team_settings, roles: dict[str, object]) -> None:
    user = make_user(roles, username="user")
    make_membership(user_id=user.id, status="PENDING")

    with pytest.raises(ApiError) as exc_info:
        apply_membership(user, "再次申请")

    assert exc_info.value.error == MEMBERSHIP_CHANGE_BLOCKED


def test_duplicate_review_conflict(team_settings, roles: dict[str, object]) -> None:
    admin = make_user(roles, username="admin", role_code="ORG_ADMIN")
    user = make_user(roles, username="user")
    membership = make_membership(user_id=user.id, status="PENDING")

    review_application(admin, membership.id, "APPROVE", "")
    with pytest.raises(ApiError) as exc_info:
        review_application(admin, membership.id, "APPROVE", "")

    assert exc_info.value.error == STATE_CONFLICT


def test_concurrent_reviews_produce_one_success(team_settings, roles: dict[str, object]) -> None:
    admin = make_user(roles, username="admin", role_code="ORG_ADMIN")
    user = make_user(roles, username="user")
    membership = make_membership(user_id=user.id, status="PENDING")
    results: list[object] = []
    errors: list[object] = []
    barrier = threading.Barrier(2)

    def review() -> None:
        barrier.wait()
        try:
            results.append(review_application(admin, membership.id, "APPROVE", ""))
        except (ApiError, OperationalError) as exc:
            errors.append(exc)

    threads = [threading.Thread(target=review) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 1
    assert len(errors) == 1
    membership.refresh_from_db()
    assert membership.status == "ACTIVE"
