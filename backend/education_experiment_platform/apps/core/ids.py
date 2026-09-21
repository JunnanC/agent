"""ULID 生成（doc 01 §一 原则 6、doc 07 §一）。

doc 07：``public_id CHAR(26)`` ULID、唯一、ASCII binary collation；URL/API 不接受自增主键。

为什么自己实现而不是装 ``python-ulid``：项目依赖锁是评审过的（``requirements/*.txt``），
为一个 20 行的纯函数新增运行时依赖不划算。ULID 规格是稳定的：
48 位毫秒时间戳 + 80 位随机数的 Crockford Base32，共 26 字符。
"""

from __future__ import annotations

import secrets
import time

# Crockford Base32：去掉了 I、L、O、U，避免与 1、0 混淆。
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_TIME_CHARS = 10
_RANDOM_CHARS = 16
_MAX_TIMESTAMP_MS = 1 << 48


def new_ulid(now_ms: int | None = None) -> str:
    """生成一个 26 字符 ULID，字典序即时间序。"""
    timestamp = int(time.time() * 1000) if now_ms is None else now_ms
    if not 0 <= timestamp < _MAX_TIMESTAMP_MS:
        raise ValueError("ULID 时间戳必须是 48 位无符号整数")
    return _encode(timestamp, _TIME_CHARS) + _encode(secrets.randbits(80), _RANDOM_CHARS)


def _encode(value: int, length: int) -> str:
    chars = [_ALPHABET[0]] * length
    for index in range(length - 1, -1, -1):
        chars[index] = _ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(chars)
