from __future__ import annotations

import pytest

from apps.common.errors import (
    LAST_TEAM_ADMIN_PROTECTED,
    MEMBERSHIP_CHANGE_BLOCKED,
    ApiError,
)
from apps.common.models import AuditLog, OutboxEvent
from apps.membership.blocking import BlockItem
from apps.membership.services import (
    apply_membership,
    assert_member_active,
    direct_add_member,
    exit_membership,
    get_active_membership_id,
    is_active_member,
    remove_membership,
    review_application,
)

from .conftest import make_membership, make_user


def test_apply_review_and_realtime_membership(team_settings, roles: dict[str, object]) -> None:
    applicant = make_user(roles, username="applicant")
    admin = make_user(roles, username="admin", role_code="ORG_ADMIN")

    membership = apply_membership(applicant, "申请加入团队")
    approved = review_application(admin, membership.id, "APPROVE", "")

    assert membership.status == "PENDING"
    assert approved.status == "ACTIVE"
    assert approved.previous_status == "PENDING"
    assert approved.reviewed_by_id == admin.id
    assert is_active_member(applicant.id) is True
    assert get_active_membership_id(applicant.id) == approved.id
    assert assert_member_active(applicant.id) == approved.id
    assert OutboxEvent.objects.filter(event_type="membership.applied").count() == 1
    assert OutboxEvent.objects.filter(event_type="membership.approved").count() == 1
    assert AuditLog.objects.filter(action="membership.apply").count() == 1
    assert AuditLog.objects.filter(action="membership.review").count() == 1


def test_direct_add_and_remove_member(team_settings, roles: dict[str, object]) -> None:
    admin = make_user(roles, username="admin", role_code="ORG_ADMIN")
    member_user = make_user(roles, username="member")

    membership = direct_add_member(admin, "member")
    removed = remove_membership(admin, membership.id, "违规使用")

    assert membership.status == "ACTIVE"
    assert membership.join_source == "DIRECT"
    assert removed.status == "REMOVED"
    assert removed.removed_at is not None
    assert is_active_member(member_user.id) is False
    assert OutboxEvent.objects.filter(event_type="membership.added").count() == 1
    assert OutboxEvent.objects.filter(event_type="membership.removed").count() == 1
    assert (
        OutboxEvent.objects.filter(event_type="workspace.session.revocation.requested").count() == 1
    )


def test_exit_membership_publishes_session_revocation(
    team_settings, roles: dict[str, object]
) -> None:
    user = make_user(roles, username="member")
    make_membership(user_id=user.id, status="ACTIVE")

    exited = exit_membership(user, "个人原因")

    assert exited.status == "EXITED"
    assert exited.exited_at is not None
    assert OutboxEvent.objects.filter(event_type="membership.exited").count() == 1
    assert (
        OutboxEvent.objects.filter(event_type="workspace.session.revocation.requested").count() == 1
    )


def test_exit_membership_is_blocked_with_details(
    team_settings,
    roles: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(roles, username="member")
    membership = make_membership(user_id=user.id, status="ACTIVE")
    blocker = BlockItem(
        type="unfinished_assignment",
        assignment_id="assignment-1",
        status="UNDER_REVIEW",
        reason="报告待审核",
    )
    monkeypatch.setattr(
        "apps.membership.services.has_blocking_items",
        lambda _user_id, operation="exit": [blocker],
    )

    with pytest.raises(ApiError) as exc_info:
        exit_membership(user, "个人原因")

    membership.refresh_from_db()
    assert exc_info.value.error == MEMBERSHIP_CHANGE_BLOCKED
    assert membership.status == "ACTIVE"
    assert membership.last_block_check_json == [blocker.as_dict()]
    assert exc_info.value.details == [blocker.as_dict()]


def test_remove_last_org_admin_is_protected(team_settings, roles: dict[str, object]) -> None:
    actor = make_user(roles, username="actor", role_code="ORG_ADMIN")
    target = make_user(roles, username="target", role_code="ORG_ADMIN")
    membership = make_membership(user_id=target.id, status="ACTIVE")

    with pytest.raises(ApiError) as exc_info:
        remove_membership(actor, membership.id, "调整团队")

    assert exc_info.value.error == LAST_TEAM_ADMIN_PROTECTED
    membership.refresh_from_db()
    assert membership.status == "ACTIVE"
