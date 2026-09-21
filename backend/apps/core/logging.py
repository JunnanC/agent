import json
import logging
import re
from datetime import datetime, timezone

from django.conf import settings

from apps.core.tracing import (
    current_celery_queue,
    current_portal,
    current_trace_id,
    new_trace_id,
)


REDACTED = "***REDACTED***"
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:password|passwd|secret|credential|authorization|cookie|session"
    r"|csrf|token|api[_-]?key|access[_-]?key|prompt|signature[_-]?url"
    r"|signed[_-]?url|id[_-]?(?:number|card)|identity)",
    re.IGNORECASE,
)
FULL_VALUE_SENSITIVE_PATTERN = re.compile(
    r"(?i)\b(prompt|authorization|credential|id[_-]?number|id[_-]?card"
    r"|identity)\b\s*[:=]\s*.+"
)
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)\b(password|passwd|secret|credential|authorization|cookie"
    r"|session[_-]?id|csrf[_-]?token|workspace[_-]?token|api[_-]?key"
    r"|access[_-]?key|prompt|signature[_-]?url|signed[_-]?url)\b"
    r"[\"']?\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;}\]]+)"
)
SIGNED_URL_PATTERN = re.compile(r"(?i)\bhttps?://[^\s\"']+")


def _redact_string(value: str) -> str:
    value = FULL_VALUE_SENSITIVE_PATTERN.sub(
        lambda match: f"{match.group(1)}={REDACTED}",
        value,
    )
    value = SENSITIVE_VALUE_PATTERN.sub(
        lambda match: f"{match.group(1)}={REDACTED}",
        value,
    )
    return SIGNED_URL_PATTERN.sub(
        lambda match: (
            REDACTED
            if any(
                marker in match.group(0).lower()
                for marker in ("signature", "x-amz-signature", "signedurl")
            )
            else match.group(0)
        ),
        value,
    )


def _redact_value(value):
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, dict):
        return {
            key: REDACTED if SENSITIVE_KEY_PATTERN.search(str(key)) else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    return value


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact_string(record.getMessage())
        record.args = ()
        return True


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        try:
            payload = self._payload(record)
            return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return self._fallback(record)

    def _payload(self, record: logging.LogRecord) -> dict:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": settings.SERVICE_NAME,
            "portal": current_portal(),
            "trace_id": current_trace_id() or new_trace_id(),
            "message": record.getMessage(),
        }
        queue = current_celery_queue()
        if queue:
            payload["celery_queue"] = queue
        for field in (
            "actor_opaque_id",
            "course_opaque_id",
            "task_opaque_id",
            "action",
            "result",
            "error_code",
            "duration_ms",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return _redact_value(payload)

    def _fallback(self, record: logging.LogRecord) -> str:
        try:
            message = record.getMessage()
        except Exception:
            message = record.msg
        timestamp = datetime.fromtimestamp(
            record.created,
            tz=timezone.utc,
        ).isoformat().replace("+00:00", "Z")
        return f"{timestamp} {record.levelname} {settings.SERVICE_NAME} {message}"
