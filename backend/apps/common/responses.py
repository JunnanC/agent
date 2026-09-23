"""Backward-compatible import path for the core response contract."""

from apps.core.responses import accepted, failure, json_response, paginated, success

__all__ = ["accepted", "failure", "json_response", "paginated", "success"]
