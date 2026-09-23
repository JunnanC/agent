"""Compatibility aliases; cross-module persistence contracts live in core."""

from apps.core.models import AuditLog, OutboxEvent

__all__ = ["AuditLog", "OutboxEvent"]
