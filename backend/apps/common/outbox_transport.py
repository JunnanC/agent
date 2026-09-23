"""Compatibility aliases for core Outbox transports."""

from apps.core.outbox_transport import OutboxTransport, RedisStreamTransport

__all__ = ["OutboxTransport", "RedisStreamTransport"]
