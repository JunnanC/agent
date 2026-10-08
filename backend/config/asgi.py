import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# Lazy import to avoid circular dependency at module load time.
_http_app = None


def _get_http_app():
    global _http_app
    if _http_app is None:
        _http_app = get_asgi_application()
    return _http_app


class ProtocolRouter:
    """Dispatch ASGI connections by protocol type.

    HTTP  → Django WSGI-to-ASGI adapter (views, DRF, static…).
    WS    → lightweight consumers defined in apps.common.ws.
    """

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            from apps.common.ws import websocket_application
            await websocket_application(scope, receive, send)
        elif scope["type"] == "http":
            await _get_http_app()(scope, receive, send)
        else:
            raise ValueError(f"Unsupported ASGI protocol: {scope[type]}")


application = ProtocolRouter()
