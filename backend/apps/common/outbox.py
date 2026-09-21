from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction

from .context import current_trace_id
from .errors import INTERNAL_ERROR, ApiError
from .logging import mask_sensitive
from .models import OutboxEvent
from .outbox_transport import OutboxTransport, RedisStreamTransport


@dataclass(frozen=True)
class OutboxMessage:
    event_type: str
    occurred_at: datetime
    trace_id: str
    aggregate_type: str
    aggregate_id: str
    topic: str
    assignment_id: str | None = None
    instance_id: str | None = None
    operation_id: str | None = None
    extra_payload: dict[str, Any] | None = None
    event_id: str | None = None


def publish_outbox(message: OutboxMessage, *, available_at: datetime | None = None) -> OutboxEvent:
    connection = transaction.get_connection()
    if not connection.in_atomic_block:
        raise ApiError(INTERNAL_ERROR, message="Outbox必须在数据库事务内发布")

    now = datetime.now(UTC)
    event_id = message.event_id or str(uuid.uuid4())
    payload: dict[str, Any] = {
        "event_id": event_id,
        "event_type": message.event_type,
        "occurred_at": message.occurred_at.astimezone(UTC).isoformat(),
        "trace_id": message.trace_id,
        "aggregate_type": message.aggregate_type,
        "aggregate_id": message.aggregate_id,
        **(message.extra_payload or {}),
    }
    for field in ("assignment_id", "instance_id", "operation_id"):
        value = getattr(message, field)
        if value is not None:
            payload[field] = value

    return OutboxEvent.objects.create(
        event_id=event_id,
        event_type=message.event_type,
        aggregate_type=message.aggregate_type,
        aggregate_id=message.aggregate_id,
        assignment_id=message.assignment_id,
        instance_id=message.instance_id,
        topic=message.topic,
        payload_json=mask_sensitive(payload),
        status="PENDING",
        attempt_count=0,
        available_at=available_at or now,
        published_at=None,
        last_error="",
        trace_id=message.trace_id or current_trace_id(),
        created_at=now,
    )


def dispatch_due_outbox(limit: int | None = None, transport: OutboxTransport | None = None) -> int:
    batch_size = limit or settings.COMMON_OUTBOX_BATCH_SIZE
    publisher = transport or RedisStreamTransport()
    now = datetime.now(UTC)
    published = 0

    with transaction.atomic():
        events = (
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(status__in={"PENDING", "FAILED"}, available_at__lte=now)
            .order_by("available_at", "id")[:batch_size]
        )
        for event in events:
            payload_json = json.dumps(event.payload_json, ensure_ascii=False, sort_keys=True)
            try:
                publisher.publish(event.topic, event.event_id, payload_json)
            except Exception as exc:  # noqa: BLE001
                event.attempt_count += 1
                event.last_error = str(mask_sensitive(str(exc)))
                if event.attempt_count >= 10:
                    event.status = "DEAD"
                else:
                    event.status = "FAILED"
                    event.available_at = now + timedelta(seconds=2**event.attempt_count)
                event.save(update_fields=["status", "attempt_count", "available_at", "last_error"])
                continue

            event.status = "PUBLISHED"
            event.published_at = now
            event.last_error = ""
            event.save(update_fields=["status", "published_at", "last_error"])
            published += 1

    return published
