from __future__ import annotations

from datetime import UTC, datetime

from django.db import transaction

from apps.common.errors import QUOTA_EXCEEDED, RESOURCE_NOT_FOUND, VALIDATION_ERROR, ApiError
from apps.common.outbox import OutboxMessage, publish_outbox

from ..models import UserQuota
from ..selectors import get_user

QUOTA_FIELDS = ("instances", "cpu_millicores", "memory_mb", "disk_mb", "vm_count", "gpu_count")


def get_quota(user_id: int) -> UserQuota:
    user = get_user(user_id)
    if user is None:
        raise ApiError(RESOURCE_NOT_FOUND)
    quota = UserQuota.objects.filter(user_id=user.id).first()
    if quota is None:
        raise ApiError(RESOURCE_NOT_FOUND, message="配额记录不存在")
    return quota


def update_quota(user_id: int, max_values: dict[str, int]) -> UserQuota:
    quota = get_quota(user_id)
    for field, value in max_values.items():
        if value < 0:
            raise ApiError(VALIDATION_ERROR, message="配额上限不能为负数")
        setattr(quota, f"max_{field}", value)
    quota.updated_at = datetime.now(UTC)
    quota.save()
    return quota


def adjust_quota(user_id: int, delta: dict[str, int], idempotency_key: str) -> None:
    from apps.common.models import OutboxEvent

    if not idempotency_key:
        raise ApiError(VALIDATION_ERROR, message="幂等键不能为空")
    event_id = f"quota-adjust-{idempotency_key}"
    now = datetime.now(UTC)
    with transaction.atomic():
        if OutboxEvent.objects.filter(event_id=event_id).exists():
            return
        quota = UserQuota.objects.select_for_update().get(user_id=user_id)
        after: dict[str, int] = {}
        for suffix, amount in delta.items():
            if suffix not in QUOTA_FIELDS:
                raise ApiError(VALIDATION_ERROR, message="未知配额字段")
            used = getattr(quota, f"used_{suffix}") + amount
            maximum = getattr(quota, f"max_{suffix}")
            if used < 0 or used > maximum:
                raise ApiError(QUOTA_EXCEEDED)
            setattr(quota, f"used_{suffix}", used)
            after[suffix] = used
        quota.updated_at = now
        quota.save()
        publish_outbox(
            OutboxMessage(
                event_id=event_id,
                event_type="identity.quota.adjusted",
                occurred_at=now,
                trace_id="",
                aggregate_type="USER_QUOTA",
                aggregate_id=str(quota.user_id),
                topic="quota.adjusted",
                extra_payload={"user_id": quota.user_id, "after": after},
            )
        )
