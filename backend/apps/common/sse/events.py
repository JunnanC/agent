"""Shared Server-Sent Events wire object."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from apps.common.sse.enums import SSEEventType, SSEStage


@dataclass(frozen=True, slots=True)
class SSEEvent:
    """Wire object with exactly the twelve baseline SSE payload fields."""

    event_id: str
    event_type: SSEEventType
    occurred_at: str
    assignment_id: int
    instance_id: int
    operation_id: str
    stage: str | None
    status: str
    progress_percent: int
    message: str
    retryable: bool
    trace_id: str

    def __post_init__(self) -> None:
        UUID(self.event_id)
        UUID(self.operation_id)
        UUID(self.trace_id)
        if not 0 <= self.progress_percent <= 100:
            raise ValueError("PROGRESS_OUT_OF_RANGE")

    @classmethod
    def create(
        cls,
        *,
        event_type: SSEEventType,
        assignment_id: int,
        instance_id: int,
        operation_id: str,
        status: str | StrEnum,
        message: str,
        trace_id: str,
        stage: str | SSEStage | None = None,
        progress_percent: int = 0,
        retryable: bool = False,
        occurred_at: datetime | None = None,
        event_id: str | None = None,
    ) -> SSEEvent:
        timestamp = occurred_at or datetime.now(UTC)
        return cls(
            event_id=event_id or str(uuid4()),
            event_type=event_type,
            occurred_at=timestamp.astimezone(UTC).isoformat(),
            assignment_id=assignment_id,
            instance_id=instance_id,
            operation_id=operation_id,
            stage=str(stage) if stage is not None else None,
            status=str(status),
            progress_percent=progress_percent,
            message=message,
            retryable=retryable,
            trace_id=trace_id,
        )

    def payload(self) -> dict[str, Any]:
        return asdict(self)

    def to_wire(self) -> str:
        lines = [f"event:{self.event_type}", f"id:{self.event_id}"]
        lines.append("data:" + json.dumps(self.payload(), ensure_ascii=False, separators=(",", ":")))
        return "\n".join(lines) + "\n\n"
