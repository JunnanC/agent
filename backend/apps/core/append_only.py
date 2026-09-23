from __future__ import annotations

"""Framework-neutral append-only fact contract.

Append-only records intentionally have no update or delete operation.  A
repository adapter supplies the atomic ``contains`` and ``append`` methods;
the core policy only decides when an event is a duplicate.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol


class AppendOnlyViolation(ValueError):
    """Raised when code tries to mutate an append-only fact."""


class AppendOnly(Protocol):
    id: int
    created_at: datetime


@dataclass(frozen=True)
class Fact:
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    occurred_at: datetime
    trace_id: str = ""

    def __post_init__(self) -> None:
        if not self.event_id or not self.event_type or not self.aggregate_type:
            raise AppendOnlyViolation("append-only facts require stable identifiers")
        if self.occurred_at.tzinfo is None:
            raise AppendOnlyViolation("occurred_at must be timezone-aware")

    @property
    def occurred_at_utc(self) -> datetime:
        return self.occurred_at.astimezone(UTC)


class FactStore(Protocol):
    def contains(self, event_id: str) -> bool: ...

    def append(self, fact: Fact) -> Any: ...


def append_once(store: FactStore, fact: Fact) -> Any:
    """Append one fact; the event id is the idempotency boundary."""
    if store.contains(fact.event_id):
        return None
    return store.append(fact)
