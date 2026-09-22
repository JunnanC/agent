"""并发控制：ETag / If-Match（doc 02 §七、doc 08 §1.1）。

约定：GET 返回 ``ETag: "<row_version>"``；管理类 PATCH 与状态写必须带
``If-Match``，与当前 ``row_version`` 一致才允许写入。

为什么用强 ETag（不带 ``W/``）：RFC 9110 规定 ``If-Match`` 使用强比较，
弱验证符永远不匹配；用弱 ETag 会让「并发保护」变成永远失败的装饰。
"""

from __future__ import annotations

import re

from django.http import HttpRequest

from .errors import PRECONDITION_REQUIRED, ROW_VERSION_CONFLICT, VALIDATION_ERROR, ApiError

IF_MATCH_HEADER = "If-Match"
_ETAG_RE = re.compile(r'^"(\d{1,10})"$')


def etag_for(row_version: int) -> str:
    return f'"{row_version}"'


def read_if_match(request: HttpRequest) -> int:
    """读取 If-Match 并解析成 row_version。"""
    raw = (request.headers.get(IF_MATCH_HEADER) or "").strip()
    if not raw:
        raise ApiError(
            PRECONDITION_REQUIRED,
            detail={"header": IF_MATCH_HEADER, "issue": "状态写入必须带 If-Match"},
        )
    match = _ETAG_RE.match(raw)
    if match is None:
        raise ApiError(
            VALIDATION_ERROR,
            detail={"header": IF_MATCH_HEADER, "issue": '需要形如 "3" 的强 ETag'},
        )
    return int(match.group(1))


def assert_row_version(*, actual: int, expected: int, target_type: str, target_id: str) -> None:
    """乐观锁校验。不一致时返回当前值，便于客户端合并后重试。"""
    if actual != expected:
        raise ApiError(
            ROW_VERSION_CONFLICT,
            detail={
                "target_type": target_type,
                "target_id": target_id,
                "expected": expected,
                "current": actual,
            },
        )
