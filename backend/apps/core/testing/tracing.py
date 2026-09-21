from contextlib import contextmanager
from typing import Iterator

from apps.core.tracing import (
    _portal,
    bind_trace_context,
    clear_trace_context,
    current_portal,
    current_trace_id,
    new_trace_id,
)


@contextmanager
def trace_context(
    trace_id: str | None = None,
    portal: str | None = None,
) -> Iterator[str]:
    resolved_trace_id = trace_id or new_trace_id()
    previous_trace_id = current_trace_id()
    previous_portal = current_portal()
    bind_trace_context(trace_id=resolved_trace_id, portal=portal)
    try:
        yield resolved_trace_id
    finally:
        clear_trace_context()
        if previous_trace_id is not None:
            bind_trace_context(
                trace_id=previous_trace_id,
                portal=previous_portal,
            )
        elif previous_portal is not None:
            _portal.set(previous_portal)


@contextmanager
def portal_context(portal: str) -> Iterator[None]:
    if portal not in {"USER", "TEACHING", "PLATFORM"}:
        raise ValueError("portal must be USER, TEACHING, PLATFORM")
    portal_token = _portal.set(portal)
    try:
        yield
    finally:
        _portal.reset(portal_token)


def fake_traceparent(trace_id: str | None = None) -> str:
    resolved_trace_id = trace_id or new_trace_id()
    return f"00-{resolved_trace_id}-{new_trace_id()[:16]}-01"
