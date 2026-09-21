from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
git remote -v
git branch -a
from django.conf import settings
from django.utils.module_loading import import_string

from .constants import (
    EXIT_BLOCKING_ASSIGNMENT_STATUSES,
    REMOVE_BLOCKING_ASSIGNMENT_STATUSES,
)


@dataclass(frozen=True)
class BlockItem:
    type: str
    assignment_id: str
    status: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {
            "type": self.type,
            "assignment_id": self.assignment_id,
            "status": self.status,
            "reason": self.reason,
        }


class BlockingProvider(Protocol):
    def get_blocking_items(self, user_id: int, operation: str) -> list[BlockItem]: ...


class DefaultBlockingProvider:
    def get_blocking_items(self, user_id: int, operation: str) -> list[BlockItem]:
        return []


class TaskStatsProvider(Protocol):
    def get_blocking_count(self, user_id: int) -> int: ...

    def get_active_task_count(self, user_id: int) -> int: ...


class DefaultTaskStatsProvider:
    def get_blocking_count(self, user_id: int) -> int:
        return 0

    def get_active_task_count(self, user_id: int) -> int:
        return 0


def blocking_provider() -> BlockingProvider:
    path = getattr(settings, "MEMBERSHIP_BLOCKING_PROVIDER", "")
    if not path:
        return DefaultBlockingProvider()
    provider = import_string(path)
    return provider() if isinstance(provider, type) else provider


def task_stats_provider() -> TaskStatsProvider:
    path = getattr(settings, "MEMBERSHIP_TASK_STATS_PROVIDER", "")
    if not path:
        return DefaultTaskStatsProvider()
    provider = import_string(path)
    return provider() if isinstance(provider, type) else provider


def has_blocking_items(user_id: int, *, operation: str = "exit") -> list[BlockItem]:
    if operation not in {"exit", "remove"}:
        raise ValueError("operation must be exit or remove")
    return blocking_provider().get_blocking_items(user_id, operation)


def blocking_statuses(operation: str) -> set[str]:
    if operation == "exit":
        return EXIT_BLOCKING_ASSIGNMENT_STATUSES
    if operation == "remove":
        return REMOVE_BLOCKING_ASSIGNMENT_STATUSES
    raise ValueError("operation must be exit or remove")
