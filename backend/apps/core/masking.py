from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

MASK = "***"
SENSITIVE_KEYS = {
    "password",
    "passwd",
    "token",
    "accesstoken",
    "refreshtoken",
    "authorization",
    "cookie",
    "apikey",
    "apisecret",
    "secretkey",
    "clientsecret",
}
_BEARER_PATTERN = re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+")
_API_KEY_PATTERN = re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s,;]+")
_COOKIE_PATTERN = re.compile(r"(?i)(cookie\s*[=:]\s*)[^\r\n]+")
_SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(password|passwd|token|authorization|cookie|api[_-]?key|secret)\s*[=:]\s*[^\s,;]+"
)
_SECRET_VALUE_PATTERN = re.compile(r"(?i)\b[a-z0-9._~+-]*secret[a-z0-9._~+-]*\b")


def _normalize_key(key: str) -> str:
    return "".join(character for character in key.lower() if character.isalnum())


def _mask_string(value: str) -> str:
    masked = _BEARER_PATTERN.sub(lambda match: match.group(1) + MASK, value)
    masked = _API_KEY_PATTERN.sub(lambda match: match.group(1) + MASK, masked)
    masked = _COOKIE_PATTERN.sub(lambda match: match.group(1) + MASK, masked)
    masked = re.sub(r"(?i)(session\s*[=:]\s*)[^\s,;]+", lambda match: match.group(1) + MASK, masked)
    masked = _SENSITIVE_ASSIGNMENT_PATTERN.sub(lambda match: match.group(1) + "=" + MASK, masked)
    return _SECRET_VALUE_PATTERN.sub(MASK, masked)


def mask_sensitive(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: MASK if _normalize_key(str(key)) in SENSITIVE_KEYS else mask_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [mask_sensitive(item) for item in value]
    if isinstance(value, str):
        return _mask_string(value)
    return value


def mask_phone(value: str | None) -> str | None:
    if not value:
        return value
    if len(value) <= 7:
        return "*" * len(value)
    return f"{value[:3]}{'*' * (len(value) - 7)}{value[-4:]}"


def mask_email(value: str | None) -> str | None:
    if not value or "@" not in value:
        return value
    local, domain = value.split("@", 1)
    if len(local) <= 1:
        masked_local = "*"
    else:
        masked_local = local[0] + "***"
    return f"{masked_local}@{domain}"
