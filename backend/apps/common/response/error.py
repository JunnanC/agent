"""Compatibility exports for the core error response adapter."""

from apps.core.errors import ApiError
from apps.core.response.error import (
    _django_error,
    _map_exception,
    api_exception_handler,
    bad_request_view,
    error_response,
    not_found_view,
    permission_denied_view,
    server_error_view,
)

__all__ = [
    "ApiError",
    "_django_error",
    "_map_exception",
    "api_exception_handler",
    "bad_request_view",
    "error_response",
    "not_found_view",
    "permission_denied_view",
    "server_error_view",
]
