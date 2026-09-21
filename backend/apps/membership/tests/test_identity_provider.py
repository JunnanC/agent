from __future__ import annotations

from apps.common.models import OutboxEvent
from apps.membership.identity_provider import MembershipIdentityProvider

from .conftest import make_membership, make_user


def test_identity_provider_returns_membership_shape(
    team_settings, roles: dict[str, object]
) -> None:
    user = make_user(roles, username="provider")
    membership = make_membership(user_id=user.id, status="ACTIVE")

    result = MembershipIdentityProvider().get_membership(user.id)

    assert result == {"membership_id": str(membership.id), "status": "ACTIVE"}


def test_identity_provider_returns_none_without_membership(
    team_settings, roles: dict[str, object]
) -> None:
    user = make_user(roles, username="none")

    assert MembershipIdentityProvider().get_membership(user.id) is None


def test_identity_provider_reads_unverified_policy(team_settings) -> None:
    assert MembershipIdentityProvider().unverified_start_policy("1") == "DENIED"


def test_identity_provider_revokes_sessions_through_outbox(
    team_settings, roles: dict[str, object]
) -> None:
    user = make_user(roles, username="sessions")

    MembershipIdentityProvider().revoke_authentication_sessions(user.id)

    event = OutboxEvent.objects.get(event_type="workspace.session.revocation.requested")
    assert event.aggregate_type == "SESSION"
    assert event.aggregate_id == str(user.id)
    assert event.payload_json["user_id"] == user.id
