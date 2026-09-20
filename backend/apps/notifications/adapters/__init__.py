"""Notification adapters."""

from apps.notifications.adapters.fake import InMemoryEventSource, MemoryEventDeduplicator

__all__ = ["InMemoryEventSource", "MemoryEventDeduplicator"]
