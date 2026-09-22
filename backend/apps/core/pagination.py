from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from django.http import HttpRequest

from .errors import VALIDATION_ERROR, ApiError

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class PageParams:
    page: int = DEFAULT_PAGE
    page_size: int = DEFAULT_PAGE_SIZE
    sort: str | None = None
    order: Literal["asc", "desc"] = "desc"


@dataclass(frozen=True)
class PageResult:
    items: list[Any]
    page: int
    page_size: int
    total: int


def parse_page_params(
    request: HttpRequest, allowed_sorts: set[str], default_sort: str
) -> PageParams:
    params = request.query_params if hasattr(request, "query_params") else request.GET
    try:
        page = int(params.get("page", DEFAULT_PAGE))
        page_size = int(params.get("page_size", DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError) as exc:
        raise ApiError(
            VALIDATION_ERROR,
            message="分页参数必须为整数",
            details=[{"field": "page", "issue": "无效"}],
        ) from exc
    if page < 1:
        raise ApiError(VALIDATION_ERROR, details=[{"field": "page", "issue": "必须大于等于1"}])
    if page_size < 1:
        raise ApiError(
            VALIDATION_ERROR,
            details=[{"field": "page_size", "issue": "必须大于等于1"}],
        )

    order = str(params.get("sort_order", params.get("order", "desc"))).lower()
    if order not in {"asc", "desc"}:
        raise ApiError(
            VALIDATION_ERROR,
            details=[{"field": "order", "issue": "只允许asc或desc"}],
        )

    sort = params.get("sort", params.get("sort_by", default_sort))
    if sort not in allowed_sorts and sort != default_sort:
        raise ApiError(
            VALIDATION_ERROR,
            details=[{"field": "sort", "issue": "排序字段不在白名单"}],
        )
    return PageParams(
        page=page,
        page_size=min(page_size, MAX_PAGE_SIZE),
        sort=sort,
        order=order,
    )


def paginate_queryset(queryset: Any, params: PageParams, default_sort: str) -> PageResult:
    sort = params.sort or default_sort
    direction = "" if params.order == "asc" else "-"
    ordering = [f"{direction}{sort}"]
    if sort != "id":
        ordering.append("-id" if params.order == "desc" else "id")
    total = queryset.count()
    offset = (params.page - 1) * params.page_size
    items = list(queryset.order_by(*ordering)[offset : offset + params.page_size])
    return PageResult(items=items, page=params.page, page_size=params.page_size, total=total)
