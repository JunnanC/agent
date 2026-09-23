from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    trace_id: str
    user_id: str | None
    action: str


_context: ContextVar[RequestContext | None] = ContextVar("core_request_context", default=None)


def set_context(context: RequestContext) -> object:
    return _context.set(context)


def reset_context(token: object) -> None:
    _context.reset(token)


def current_context() -> RequestContext:
    context = _context.get()
    if context is None:
        raise RuntimeError("Request context is not active")
    return context


def current_context_or_none() -> RequestContext | None:
    return _context.get()


def current_request_id() -> str:
    context = current_context_or_none()
    return context.request_id if context else ""


def current_trace_id() -> str:
    context = current_context_or_none()
    return context.trace_id if context else ""


def current_user_id() -> str | None:
    context = current_context_or_none()
    return context.user_id if context else None


def current_action() -> str:
    context = current_context_or_none()
    return context.action if context else ""
