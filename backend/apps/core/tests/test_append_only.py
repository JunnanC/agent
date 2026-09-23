from datetime import UTC, datetime

from apps.core.append_only import Fact, append_once


class MemoryFactStore:
    def __init__(self) -> None:
        self.events: dict[str, Fact] = {}

    def contains(self, event_id: str) -> bool:
        return event_id in self.events

    def append(self, fact: Fact) -> Fact:
        self.events[fact.event_id] = fact
        return fact


def test_append_once_is_idempotent_by_event_id() -> None:
    store = MemoryFactStore()
    fact = Fact(
        event_id="event-1",
        event_type="task.transitioned",
        aggregate_type="TASK",
        aggregate_id="task-1",
        payload={"to": "READY"},
        occurred_at=datetime.now(UTC),
    )

    assert append_once(store, fact) is fact
    assert append_once(store, fact) is None
    assert list(store.events) == ["event-1"]
