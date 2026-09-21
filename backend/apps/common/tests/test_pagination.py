from __future__ import annotations

import pytest
from django.http import HttpRequest

from apps.common.errors import ApiError
from apps.common.pagination import PageParams, paginate_queryset, parse_page_params


class FakeQuerySet:
    def __init__(self, items: list[int]) -> None:
        self.items = items

    def count(self) -> int:
        return len(self.items)

    def order_by(self, *_fields: str) -> FakeQuerySet:
        return self

    def __getitem__(self, item: slice) -> list[int]:
        return self.items[item]


def _request(query: str) -> HttpRequest:
    request = HttpRequest()
    request.method = "GET"
    request.GET = {}
    for part in query.split("&"):
        if not part:
            continue
        key, value = part.split("=", 1)
        request.GET[key] = value
    return request


def test_parse_page_params_defaults_and_cap() -> None:
    params = parse_page_params(_request(""), {"created_at"}, "created_at")

    assert params == PageParams(page=1, page_size=20, sort="created_at", order="desc")

    capped = parse_page_params(_request("page_size=200"), {"created_at"}, "created_at")
    assert capped.page_size == 100


def test_parse_page_params_rejects_invalid_sort() -> None:
    with pytest.raises(ApiError):
        parse_page_params(_request("sort=password"), {"created_at"}, "created_at")


def test_parse_page_params_supports_documented_sort_aliases() -> None:
    params = parse_page_params(
        _request("sort_by=action&sort_order=asc"), {"created_at", "action"}, "created_at"
    )

    assert params.sort == "action"
    assert params.order == "asc"


def test_paginate_queryset_has_no_duplicate_or_missing_items() -> None:
    items = list(range(1, 251))
    collected: list[int] = []
    page = 1

    while True:
        result = paginate_queryset(FakeQuerySet(items), PageParams(page=page, page_size=100), "id")
        collected.extend(result.items)
        if page * 100 >= result.total:
            break
        page += 1

    assert collected == items
