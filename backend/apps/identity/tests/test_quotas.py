from __future__ import annotations

import pytest

from apps.common.errors import QUOTA_EXCEEDED
from apps.common.models import OutboxEvent

from .conftest import make_user


def test_adjust_quota_is_idempotent_and_enforces_limit(roles: dict[str, object]) -> None:
    user = make_user(roles, username="quota")
    from apps.identity.services.quotas import adjust_quota

    adjust_quota(user.id, {"instances": 2}, "same-key")
    adjust_quota(user.id, {"instances": 2}, "same-key")
    user.refresh_from_db()

    assert user.userquota.used_instances == 2
    assert OutboxEvent.objects.filter(event_id="quota-adjust-same-key").count() == 1
    from apps.common.errors import ApiError

    with pytest.raises(ApiError) as exc_info:
        adjust_quota(user.id, {"instances": 4}, "overflow")
    assert exc_info.value.error == QUOTA_EXCEEDED
