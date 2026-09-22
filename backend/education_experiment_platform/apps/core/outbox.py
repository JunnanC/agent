"""Transactional Outbox（doc 03 §二）。

链路：业务事务写 OutboxEvent + OutboxDelivery → 提交 → 中继 worker →
Redis Stream → SSE / 通知 / 投影 / 作业消费者。

为什么强制在事务内写入：如果调用方在事务外调用 ``publish_outbox``，
事件会先于业务事实落库；业务事务随后回滚时事件已经存在，
中继就会投递一个**从未发生过的事实**，而消费方无法察觉。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import OutboxDelivery, OutboxEvent

# 重试退避基数：第 n 次失败后等待 base * 2**(n-1) 秒，避免下游故障时的重试风暴。
RETRY_BACKOFF_BASE_SECONDS = 5
RETRY_BACKOFF_CAP_SECONDS = 600


def publish_outbox(
    *,
    event_name: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    trace_id: str = "",
    occurred_at: datetime | None = None,
) -> OutboxEvent:
    """在当前事务内登记一个待投递事件，返回事件行。

    调用方必须已经处于 ``transaction.atomic()`` 中；否则抛 ``RuntimeError``
    （宁可让开发期立刻失败，也不要在生产上留下永远不会回滚的孤儿事件）。
    """
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("publish_outbox 必须在事务内调用：事件与业务事实必须同一事务提交/回滚")

    moment = occurred_at or timezone.now()
    event = OutboxEvent.objects.create(
        event_name=event_name,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        trace_id=trace_id,
        occurred_at=moment,
    )
    OutboxDelivery.objects.create(
        event=event, status=OutboxDelivery.STATUS_PENDING, next_attempt_at=moment
    )
    return event


def claim_due_deliveries(*, limit: int = 100, now: datetime | None = None) -> list[int]:
    """领取到期的待投递记录 id。

    使用 ``select_for_update(skip_locked=True)``：多个中继 worker 并发时，
    已提交的记录只会被一个 worker 领走，其余 worker 跳过而不是等锁。
    """
    moment = now or timezone.now()
    with transaction.atomic():
        rows = (
            OutboxDelivery.objects.select_for_update(skip_locked=True)
            .filter(
                status__in=(OutboxDelivery.STATUS_PENDING, OutboxDelivery.STATUS_FAILED),
                next_attempt_at__lte=moment,
            )
            .order_by("next_attempt_at", "id")
            .values_list("id", flat=True)[:limit]
        )
        return list(rows)


def mark_delivered(delivery_id: int, *, now: datetime | None = None) -> None:
    moment = now or timezone.now()
    OutboxDelivery.objects.filter(id=delivery_id).update(
        status=OutboxDelivery.STATUS_DELIVERED,
        delivered_at=moment,
        attempts=_increment_attempts(delivery_id),
        last_error="",
    )


def mark_failed(
    delivery_id: int, *, error: str, max_attempts: int = 8, now: datetime | None = None
) -> None:
    """记录一次投递失败；超过 ``max_attempts`` 进入 DEAD 等待人工处理。

    DEAD 而不是继续重试：反复失败通常意味着载荷或消费方契约有问题，
    无限重试只会掩盖故障。DEAD 事件在管理端置顶（doc 03 §十）。
    """
    moment = now or timezone.now()
    delivery = OutboxDelivery.objects.get(id=delivery_id)
    attempts = delivery.attempts + 1
    if attempts >= max_attempts:
        OutboxDelivery.objects.filter(id=delivery_id).update(
            status=OutboxDelivery.STATUS_DEAD,
            attempts=attempts,
            last_error=error[:512],
        )
        return

    delay = min(RETRY_BACKOFF_BASE_SECONDS * 2 ** (attempts - 1), RETRY_BACKOFF_CAP_SECONDS)
    OutboxDelivery.objects.filter(id=delivery_id).update(
        status=OutboxDelivery.STATUS_FAILED,
        attempts=attempts,
        next_attempt_at=moment + timedelta(seconds=delay),
        last_error=error[:512],
    )


def _increment_attempts(delivery_id: int) -> int:
    delivery = OutboxDelivery.objects.filter(id=delivery_id).first()
    return (delivery.attempts + 1) if delivery else 1
