"""
Lightweight ASGI WebSocket consumers — no Django Channels dependency.

Routing
-------
/ws/echo          → EchoConsumer   (development / smoke-test)
/ws/experiment/*  → ExperimentConsumer (real-time experiment events)

Any other WS path → 404 close code.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# ── ASGI helpers ─────────────────────────────────────────


async def _ws_accept(send, subprotocol: str | None = None):
    """Send the ASGI websocket.accept message."""
    msg: dict = {"type": "websocket.accept"}
    if subprotocol:
        msg["subprotocol"] = subprotocol
    await send(msg)


async def _ws_close(send, code: int = 1000):
    """Send the ASGI websocket.close message."""
    await send({"type": "websocket.close", "code": code})


async def _ws_send_text(send, text: str):
    await send({"type": "websocket.send", "text": text})


async def _ws_send_json(send, data: dict):
    await send({"type": "websocket.send", "text": json.dumps(data)})


# ── Consumers ────────────────────────────────────────────


class EchoConsumer:
    """Echoes back every received text message.

    Lifecycle events (connect / disconnect) are logged and acknowledged
    with a welcome / goodbye JSON frame so that any WS client can verify
    the full handshake round-trip.
    """

    def __init__(self, scope):
        self.scope = scope
        self.path = scope.get("path", "")

    async def run(self, receive, send):
        await _ws_accept(send)
        await _ws_send_json(send, {"type": "welcome", "msg": "connected to echo"})
        logger.info("EchoConsumer connected: %s", self.path)

        try:
            while True:
                message = await receive()
                if message["type"] == "websocket.receive":
                    text = message.get("text", "")
                    await _ws_send_text(send, text)
                elif message["type"] == "websocket.disconnect":
                    logger.info("EchoConsumer disconnected: %s", self.path)
                    break
        except Exception:
            logger.exception("EchoConsumer error on %s", self.path)


class ExperimentConsumer:
    """Real-time experiment event stream (placeholder).

    Accepts the connection, sends a status frame, then waits for
    incoming messages.  Replace the body with Redis-pubsub or
    channel-layer fan-out once the experiment runtime is wired up.
    """

    def __init__(self, scope):
        self.scope = scope
        self.path = scope.get("path", "")

    async def run(self, receive, send):
        await _ws_accept(send)
        await _ws_send_json(send, {"type": "status", "msg": "experiment ws ready"})
        logger.info("ExperimentConsumer connected: %s", self.path)

        try:
            while True:
                message = await receive()
                if message["type"] == "websocket.receive":
                    # TODO: dispatch to experiment runtime adapter
                    await _ws_send_json(send, {"type": "ack", "echo": message.get("text")})
                elif message["type"] == "websocket.disconnect":
                    logger.info("ExperimentConsumer disconnected: %s", self.path)
                    break
        except Exception:
            logger.exception("ExperimentConsumer error on %s", self.path)


# ── Router ───────────────────────────────────────────────

_CONSUMERS = {
    "/ws/echo": EchoConsumer,
}

_PREFIX_CONSUMERS = {
    "/ws/experiment/": ExperimentConsumer,
}


async def websocket_application(scope, receive, send):
    """Entry point called by ProtocolRouter for every WS connection."""
    path = scope.get("path", "")

    # Exact match
    consumer_cls = _CONSUMERS.get(path)

    # Prefix match
    if consumer_cls is None:
        for prefix, cls in _PREFIX_CONSUMERS.items():
            if path.startswith(prefix):
                consumer_cls = cls
                break

    if consumer_cls is None:
        logger.warning("No WebSocket consumer for path: %s", path)
        await _ws_close(send, code=4004)
        return

    consumer = consumer_cls(scope)
    await consumer.run(receive, send)
