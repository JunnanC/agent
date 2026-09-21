from __future__ import annotations

import pytest

from apps.common.errors import STATE_CONFLICT, ApiError
from apps.membership.constants import MEMBERSHIP_STATUS_ACTIVE
from apps.membership.services import transition_membership

from .conftest import make_membership


def test_pending_to_active_records_previous_status(team_settings) -> None:
    membership = make_membership(user_id=1, status="PENDING")

    next_status = transition_membership(membership, "approve")

    assert next_status == MEMBERSHIP_STATUS_ACTIVE
    assert membership.status == MEMBERSHIP_STATUS_ACTIVE
    assert membership.previous_status == "PENDING"


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_illegal_transition_is_rejected(team_settings, action: str) -> None:
    membership = make_membership(user_id=1, status="ACTIVE")

    with pytest.raises(ApiError) as exc_info:
        transition_membership(membership, action)

    assert exc_info.value.error == STATE_CONFLICT
    assert membership.status == "ACTIVE"


@pytest.mark.parametrize(("action", "expected"), [("exit", "EXITED"), ("remove", "REMOVED")])
def test_active_close_transitions_are_allowed(team_settings, action: str, expected: str) -> None:
    membership = make_membership(user_id=1, status="ACTIVE")

    next_status = transition_membership(membership, action)

    assert next_status == expected
    assert membership.previous_status == "ACTIVE"
