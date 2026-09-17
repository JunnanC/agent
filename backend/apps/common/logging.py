from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .context import current_context_or_none

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
    masked = _SECRET_VALUE_PATTERN.sub(MASK, masked)
    return masked


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


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "action": record.__dict__.get("action", ""),
        }
        context = current_context_or_none()
        if context is not None:
            payload.update(
                {
                    "request_id": context.request_id,
                    "trace_id": context.trace_id,
                    "user_id": context.user_id,
                    "action": context.action,
                }
            )
        extra = getattr(record, "common_fields", None)
        if isinstance(extra, Mapping):
            payload.update(extra)
        return json.dumps(mask_sensitive(payload), ensure_ascii=False, default=str)


def json_log(action: str, *, level: int = logging.INFO, **fields: Any) -> None:
    logger = logging.getLogger("apps.common")
    context = current_context_or_none()
    payload = {
        **fields,
        "request_id": context.request_id if context else "",
        "trace_id": context.trace_id if context else "",
        "user_id": context.user_id if context else None,
        "action": action,
    }
    logger.log(
        level,
        action,
        extra={"common_fields": mask_sensitive(payload)},
    )
