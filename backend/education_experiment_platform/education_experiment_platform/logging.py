import contextvars
import json
import logging
from datetime import UTC, datetime

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
portal_var: contextvars.ContextVar[str] = contextvars.ContextVar("portal", default="")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": "django",
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id_var.get(),
            "portal": portal_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
