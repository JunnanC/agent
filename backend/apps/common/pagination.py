"""Backward-compatible import path for core pagination primitives."""

from apps.core.pagination import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PageParams,
    PageResult,
    paginate_queryset,
    parse_page_params,
)

__all__ = [
    "DEFAULT_PAGE",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "PageParams",
    "PageResult",
    "paginate_queryset",
    "parse_page_params",
]
