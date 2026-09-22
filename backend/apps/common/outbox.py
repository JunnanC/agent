"""Compatibility exports for core Outbox facts and delivery projection."""

from apps.core.outbox import OutboxMessage, dispatch_due_outbox, publish_outbox

__all__ = ["OutboxMessage", "dispatch_due_outbox", "publish_outbox"]
