from __future__ import annotations

import io
import json
import logging
from contextlib import closing

from apps.common.context import RequestContext, reset_context, set_context
from apps.common.logging import JSONFormatter, json_log, mask_sensitive


def test_mask_sensitive_mapping() -> None:
    value = {"password": "secret", "nested": {"token": "secret"}}

    assert mask_sensitive(value) == {"password": "***", "nested": {"token": "***"}}


def test_mask_sensitive_string_patterns() -> None:
    value = "Bearer abc123 api_key=xyz Cookie session=1"
    masked = mask_sensitive(value)

    assert "abc123" not in masked
    assert "xyz" not in masked
    assert "session=1" not in masked


def test_json_log_contains_context_and_fields() -> None:
    context = RequestContext("request-id", "trace-id", "1", "request.completed")
    token = set_context(context)
    logger = logging.getLogger("apps.common")
    logger.setLevel(logging.INFO)

    try:
        with closing(io.StringIO()) as stream:
            handler = logging.StreamHandler(stream)
            handler.setFormatter(JSONFormatter())
            logger.addHandler(handler)
            try:
                json_log("request.completed", status_code=200, duration_ms=1.5, token="secret")
                payload = json.loads(stream.getvalue())
            finally:
                logger.removeHandler(handler)
    finally:
        reset_context(token)

    assert payload["request_id"] == "request-id"
    assert payload["trace_id"] == "trace-id"
    assert payload["user_id"] == "1"
    assert payload["action"] == "request.completed"
    assert payload["status_code"] == 200
    assert payload["token"] == "***"
