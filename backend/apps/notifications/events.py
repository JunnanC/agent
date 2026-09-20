"""Event definitions and SSE frame helpers."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


EVENT_TASK_STATUS_CHANGED = "task.status_changed"
EVENT_ENROLLMENT_ACTIVATED = "enrollment.activated"
EVENT_PLATFORM_ALERT = "platform.alert"


EVENT_PORTAL_SCOPES = {
    EVENT_TASK_STATUS_CHANGED: {"USER"},
    EVENT_ENROLLMENT_ACTIVATED: {"USER", "TEACHING"},
    EVENT_PLATFORM_ALERT: {"PLATFORM"},
}


SENSITIVE_DATA_KEYS = {
    "session",
    "workspace_token",
    "signed_url",
    "id_number",
    "report",
}


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    event_type: str
    course_id: str | None
    subject_id: str | None
    occurred_at: str
    data: dict[str, Any]
    trace_id: str


def _sanitize_mapping(mapping: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    cleaned: dict[str, Any] = {}
    dropped: list[str] = []
    for key, value in mapping.items():
        if str(key).lower() in SENSITIVE_DATA_KEYS:
            dropped.append(str(key))
            continue
        if isinstance(value, dict):
            value, nested_dropped = _sanitize_mapping(value)
            dropped.extend(nested_dropped)
        cleaned[str(key)] = value
    return cleaned, dropped


def build_event(
    *,
    event_id: str,
    event_type: str,
    course_id: str | None = None,
    subject_id: str | None = None,
    occurred_at: str,
    data: dict[str, Any] | None = None,
    trace_id: str,
    **extra: Any,
) -> DomainEvent:
    """Build a domain event and drop fields outside the envelope whitelist."""
    if extra:
        logger.warning(
            "SSE envelope dropped extra fields: %s",
            ",".join(sorted(extra)),
        )

    cleaned_data, dropped_data_keys = _sanitize_mapping(data or {})
    if dropped_data_keys:
        logger.warning(
            "SSE event data dropped sensitive fields: %s",
            ",".join(sorted(set(dropped_data_keys))),
        )

    return DomainEvent(
        event_id=event_id,
        event_type=event_type,
        course_id=course_id,
        subject_id=subject_id,
        occurred_at=occurred_at,
        data=cleaned_data,
        trace_id=trace_id,
    )


def encode_sse_frame(event: DomainEvent) -> str:
    payload = {
        "course_id": event.course_id,
        "subject_id": event.subject_id,
        "occurred_at": event.occurred_at,
        "data": event.data,
        "trace_id": event.trace_id,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        f"id: {event.event_id}\n"
        f"event: {event.event_type}\n"
        f"data: {encoded}\n\n"
    )


def heartbeat_frame() -> str:
    return ": heartbeat\n\n"


def resync_required_frame(last_event_id: str | None) -> str:
    payload = {
        "reason": "last_event_id_out_of_window",
        "last_event_id": last_event_id,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    event_id = last_event_id or "0-0"
    return (
        f"id: {event_id}\n"
        "event: resync.required\n"
        f"data: {encoded}\n\n"
    )


def event_allowed_for_portal(event: DomainEvent, portal: str) -> bool:
    return portal in EVENT_PORTAL_SCOPES.get(event.event_type, set())
