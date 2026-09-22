from __future__ import annotations

from typing import Protocol

import redis
from django.conf import settings


class OutboxTransport(Protocol):
    def publish(self, topic: str, event_id: str, payload_json: str) -> None: ...


class RedisStreamTransport:
    def __init__(self) -> None:
        self.client = redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)

    def publish(self, topic: str, event_id: str, payload_json: str) -> None:
        self.client.xadd(topic, {"event_id": event_id, "payload_json": payload_json})
