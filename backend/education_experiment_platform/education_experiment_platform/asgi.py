import os
from collections.abc import Awaitable, Callable
from typing import Any

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "education_experiment_platform.settings.local")

django_application = get_asgi_application()


async def application(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    if scope["type"] == "websocket" and scope.get("path") == "/workspace/health":
        await receive()
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.send", "text": "workspace-gateway-ready"})
        await send({"type": "websocket.close", "code": 1000})
        return
    await django_application(scope, receive, send)
