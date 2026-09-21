"""Celery integration for M3 runtime orchestration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from .enums import CompensationFailureStage, CompensationStatus

OUTBOX_MAX_ATTEMPTS = 10
DEFAULT_MAX_AUTO_RETRIES = 5


@dataclass(frozen=True, slots=True)
class WorkerTaskRequest:
    task_name: str
    operation_id: str
    trace_id: str
    payload: Mapping[str, object]


class TaskBroker(Protocol):
    def send_task(self, task_name: str, payload: Mapping[str, object]) -> str:
        """Enqueue a task and return a broker-side task ID."""


class InlineTaskBroker:
    """Development/test broker used when the Celery process is unavailable."""

    def __init__(self, handler: Callable[[WorkerTaskRequest], None]) -> None:
        self.handler = handler
        self.sent: list[WorkerTaskRequest] = []

    def send_task(self, task_name: str, payload: Mapping[str, object]) -> str:
        request = WorkerTaskRequest(
            task_name=task_name,
            operation_id=str(payload["operation_id"]),
            trace_id=str(payload["trace_id"]),
            payload=payload,
        )
        self.sent.append(request)
        self.handler(request)
        return f"inline-{len(self.sent)}"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = DEFAULT_MAX_AUTO_RETRIES
    initial_backoff_seconds: int = 2
    backoff_multiplier: int = 2

    def delay_for_attempt(self, attempt: int) -> int:
        if attempt <= 0:
            raise ValueError("ATTEMPT_MUST_BE_POSITIVE")
        return min(
            self.initial_backoff_seconds * (self.backoff_multiplier ** (attempt - 1)),
            300,
        )

    def requires_manual_handling(self, attempt: int) -> bool:
        return attempt >= self.max_attempts


def compensation_after_retries(
    attempt: int, failure_stage: CompensationFailureStage
) -> CompensationStatus:
    policy = RetryPolicy()
    return CompensationStatus.MANUAL if policy.requires_manual_handling(attempt) else CompensationStatus.PENDING
