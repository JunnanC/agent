"""SSE event object and canonical M3 event dictionary."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from .enums import InstanceStatus


class SSEEventType(StrEnum):
    PROVISIONING_STEP_UPDATED = "PROVISIONING_STEP_UPDATED"
    PROVISIONING_COMPLETED = "PROVISIONING_COMPLETED"
    PROVISIONING_FAILED = "PROVISIONING_FAILED"
    PROVISIONING_CANCELLED = "PROVISIONING_CANCELLED"
    ARCHIVE_STEP_UPDATED = "ARCHIVE_STEP_UPDATED"
    ARCHIVE_COMPLETED = "ARCHIVE_COMPLETED"
    ARCHIVE_FAILED = "ARCHIVE_FAILED"
    DESTROY_STEP_UPDATED = "DESTROY_STEP_UPDATED"
    DESTROY_COMPLETED = "DESTROY_COMPLETED"
    INSTANCE_STATE_CHANGED = "INSTANCE_STATE_CHANGED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    TASK_WITHDRAWN = "TASK_WITHDRAWN"


class SSEStage(StrEnum):
    IMAGE_PULL = "IMAGE_PULL"
    MATERIAL_MOUNT = "MATERIAL_MOUNT"
    DEPENDENCY_RESTORE = "DEPENDENCY_RESTORE"
    HEALTH_CHECK = "HEALTH_CHECK"
    CREDENTIAL_ISSUE = "CREDENTIAL_ISSUE"
    SNAPSHOT = "SNAPSHOT"
    LOG_COLLECT = "LOG_COLLECT"
    ARTIFACT_COPY = "ARTIFACT_COPY"
    MANIFEST_VERIFY = "MANIFEST_VERIFY"
    SESSION_REVOKE = "SESSION_REVOKE"
    RUNTIME_STOP = "RUNTIME_STOP"
    RUNTIME_DESTROY = "RUNTIME_DESTROY"
    QUOTA_RELEASE = "QUOTA_RELEASE"


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
        status: str | InstanceStatus,
        message: str,
        trace_id: str,
        stage: str | SSEStage | None = None,
        progress_percent: int = 0,
        retryable: bool = False,
        occurred_at: datetime | None = None,
        event_id: str | None = None,
    ) -> "SSEEvent":
        timestamp = occurred_at or datetime.now(timezone.utc)
        return cls(
            event_id=event_id or str(uuid4()),
            event_type=event_type,
            occurred_at=timestamp.astimezone(timezone.utc).isoformat(),
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
