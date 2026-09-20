"""Ports for notification event streaming."""

from __future__ import annotations

from typing import Iterator, Protocol

from apps.notifications.events import DomainEvent


class EventSource(Protocol):
    def stream(
        self,
        portal: str,
        last_event_id: str | None = None,
    ) -> Iterator[DomainEvent]:
        """Return events visible to the portal after the last event id."""

    def has_event(self, event_id: str) -> bool:
        """Return whether an event id is still inside the resume window."""


class EventDeduplicator(Protocol):
    def seen(self, event_id: str) -> bool:
        """Return whether an event id was already emitted in this window."""

    def mark_seen(self, event_id: str) -> None:
        """Record an event id in the deduplication window."""


class EventRelay(Protocol):
    """Reserved interface for the future Redis Stream relay."""

    def publish(self, event: DomainEvent) -> None:
        """Publish an event to the relay."""

    def consume(self) -> Iterator[DomainEvent]:
        """Consume events from the relay."""
