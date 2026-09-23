from __future__ import annotations

"""Logging adapter; masking policy lives in :mod:`apps.core.masking`."""

import json
import logging
from collections.abc import Mapping
from typing import Any

from apps.core.masking import MASK, SENSITIVE_KEYS, mask_sensitive

from .context import current_context_or_none


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
    logger.log(level, action, extra={"common_fields": mask_sensitive(payload)})


__all__ = ["MASK", "SENSITIVE_KEYS", "JSONFormatter", "json_log", "mask_sensitive"]
