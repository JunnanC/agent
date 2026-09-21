from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from django.test import override_settings

from apps.common.context import RequestContext, reset_context, set_context
from apps.common.errors import ApiError
from apps.common.models import OutboxEvent
from apps.common.outbox import OutboxMessage, dispatch_due_outbox, publish_outbox


def _message() -> OutboxMessage:
    return OutboxMessage(
        event_type="generic.updated",
        occurred_at=datetime.now(UTC),
        trace_id="trace-id",
        aggregate_type="SESSION",
        aggregate_id="aggregate-id",
        topic="generic-events",
        assignment_id="opaque-assignment-id",
        instance_id="opaque-instance-id",
        operation_id="operation-id",
        extra_payload={"token": "secret-token"},
    )


def test_outbox_model_is_unmanaged() -> None:
    assert OutboxEvent._meta.managed is False
    assert OutboxEvent._meta.db_table == "outbox_events"


def test_publish_outbox_requires_transaction() -> None:
    with pytest.raises(ApiError):
        publish_outbox(_message())


def test_publish_outbox_creates_masked_payload(common_tables: None) -> None:
    token = set_context(RequestContext("request-id", "trace-id", "1", "test"))
    try:
        event = publish_outbox(_message())
    finally:
        reset_context(token)

    assert event.event_id
    assert event.status == "PENDING"
    assert event.payload_json["event_id"] == event.event_id
    assert event.payload_json["event_type"] == "generic.updated"
    assert event.payload_json["trace_id"] == "trace-id"
    assert event.payload_json["assignment_id"] == "opaque-assignment-id"
    assert event.payload_json["instance_id"] == "opaque-instance-id"
    assert event.payload_json["operation_id"] == "operation-id"
    assert event.payload_json["token"] == "***"


def test_outbox_rolls_back_with_business_transaction(common_tables: None) -> None:
    from django.db import transaction

    with pytest.raises(RuntimeError), transaction.atomic():
        publish_outbox(_message())
        raise RuntimeError("rollback")

    assert not OutboxEvent.objects.exists()


class RecordingTransport:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, str]] = []

    def publish(self, topic: str, event_id: str, payload_json: str) -> None:
        self.published.append((topic, event_id, payload_json))


class FailingTransport:
    def publish(self, topic: str, event_id: str, payload_json: str) -> None:
        raise RuntimeError("secret-token")


def test_dispatch_due_outbox_publishes_event(common_tables: None) -> None:
    event = publish_outbox(_message(), available_at=datetime.now(UTC) - timedelta(seconds=1))
    transport = RecordingTransport()

    assert dispatch_due_outbox(transport=transport) == 1
    event.refresh_from_db()

    assert event.status == "PUBLISHED"
    assert event.published_at is not None
    assert transport.published[0][0] == "generic-events"
    assert transport.published[0][1] == event.event_id


@override_settings(COMMON_OUTBOX_BATCH_SIZE=1)
def test_dispatch_due_outbox_respects_configured_batch_size(common_tables: None) -> None:
    publish_outbox(_message(), available_at=datetime.now(UTC) - timedelta(seconds=2))
    publish_outbox(_message(), available_at=datetime.now(UTC) - timedelta(seconds=1))

    assert dispatch_due_outbox(transport=RecordingTransport()) == 1


def test_dispatch_due_outbox_failure_masks_error_and_retries(
    common_tables: None,
) -> None:
    event = publish_outbox(_message(), available_at=datetime.now(UTC) - timedelta(seconds=1))

    assert dispatch_due_outbox(transport=FailingTransport()) == 0
    event.refresh_from_db()

    assert event.status == "FAILED"
    assert event.attempt_count == 1
    assert event.available_at > datetime.now(UTC)
    assert "secret-token" not in event.last_error

    event.available_at = datetime.now(UTC) - timedelta(seconds=1)
    event.save(update_fields=["available_at"])
    assert dispatch_due_outbox(transport=FailingTransport()) == 0
    event.refresh_from_db()
    assert event.attempt_count == 2


def test_dispatch_due_outbox_marks_dead_after_ten_attempts(
    common_tables: None,
) -> None:
    event = publish_outbox(_message(), available_at=datetime.now(UTC))
    event.attempt_count = 9
    event.save(update_fields=["attempt_count"])

    assert dispatch_due_outbox(transport=FailingTransport()) == 0
    event.refresh_from_db()

    assert event.status == "DEAD"
    assert event.attempt_count == 10
