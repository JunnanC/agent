import re
import uuid
from contextvars import ContextVar


TRACEPARENT_PATTERN = re.compile(
    r"^00-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}$"
)

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_portal: ContextVar[str | None] = ContextVar("portal", default=None)
_celery_queue: ContextVar[str | None] = ContextVar("celery_queue", default=None)


def bind_trace_context(*, trace_id: str, portal: str | None = None) -> None:
    normalized_trace_id = trace_id.lower()
    if not re.fullmatch(r"[0-9a-f]{32}", normalized_trace_id):
        raise ValueError("trace_id must be 32 lowercase hexadecimal characters")
    if portal not in {"USER", "TEACHING", "PLATFORM", None}:
        raise ValueError("portal must be USER, TEACHING, PLATFORM, or None")
    _trace_id.set(normalized_trace_id)
    _portal.set(portal)


def current_trace_id() -> str | None:
    return _trace_id.get()


def current_portal() -> str | None:
    return _portal.get()


def bind_celery_queue(queue: str | None) -> None:
    _celery_queue.set(queue)


def current_celery_queue() -> str | None:
    return _celery_queue.get()


def clear_trace_context() -> None:
    _trace_id.set(None)
    _portal.set(None)
    _celery_queue.set(None)


def new_trace_id() -> str:
    return uuid.uuid4().hex


def trace_headers() -> dict[str, str]:
    trace_id = current_trace_id()
    if trace_id is None:
        return {}
    return {"traceparent": f"00-{trace_id}-{uuid.uuid4().hex[:16]}-01"}


def trace_id_from_traceparent(traceparent: str) -> str | None:
    match = TRACEPARENT_PATTERN.fullmatch(traceparent.lower())
    return match.group(1) if match else None
