"""Fake in-memory event source and deduplicator."""

from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

from apps.notifications.events import DomainEvent


class InMemoryEventSource:
    def __init__(self, events: Iterable[DomainEvent] | None = None):
        self._events = list(events or [])

    def inject(self, event: DomainEvent) -> None:
        self._events.append(event)

    def has_event(self, event_id: str) -> bool:
        return any(event.event_id == event_id for event in self._events)

    def stream(
        self,
        portal: str,
        last_event_id: str | None = None,
    ):
        start = 0
        if last_event_id is not None:
            for index, event in enumerate(self._events):
                if event.event_id == last_event_id:
                    start = index + 1
                    break
            else:
                return

        yield from self._events[start:]


class MemoryEventDeduplicator:
    def __init__(self, max_size: int = 128):
        self.max_size = max_size
        self._seen: OrderedDict[str, None] = OrderedDict()

    def seen(self, event_id: str) -> bool:
        return event_id in self._seen

    def mark_seen(self, event_id: str) -> None:
        if event_id in self._seen:
            self._seen.move_to_end(event_id)
            return
        self._seen[event_id] = None
        if len(self._seen) > self.max_size:
            self._seen.popitem(last=False)
