"""The single HTTP envelope used by new API endpoints."""

from .schema import accepted, error, failure, paginated, success

__all__ = ["accepted", "error", "failure", "paginated", "success"]
