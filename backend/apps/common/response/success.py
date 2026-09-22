"""Compatibility exports for the core success response adapter."""

from apps.core.response.success import (
    accepted_response,
    created_response,
    get_trace_id,
    no_content_response,
    success_response,
)

__all__ = [
    "accepted_response",
    "created_response",
    "get_trace_id",
    "no_content_response",
    "success_response",
]
