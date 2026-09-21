from __future__ import annotations

import io
import json
import logging
import re
from contextlib import contextmanager
from typing import Iterator

from apps.core.logging import StructuredJsonFormatter


ERROR_ENVELOPE_KEYS = {"code", "message", "details", "trace_id"}
EVENT_ENVELOPE_KEYS = {"course_id", "subject_id", "occurred_at", "data", "trace_id"}
OBJECT_STORAGE_MARKERS = (
    "minio",
    "bucket",
    "x-accel-redirect",
    "localhost:9000",
    "127.0.0.1:9000",
    "minio.internal",
)
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)\b(?:password|passwd|secret|credential|authorization|cookie"
    r"|session(?:[_-]?id)?|csrf(?:[_-]?token)?|workspace[_-]?token"
    r"|one[_-]?time[_-]?token|api[_-]?key|access[_-]?key"
    r"|id[_-]?(?:number|card)|identity)\b[\"']?\s*[:=]\s*"
    r"(?:\"[^\"]+\"|'[^']+'|[^\s,;}\]]+)"
)
SIGNED_URL_PATTERN = re.compile(
    r"(?i)\bhttps?://[^\s\"']*(?:signature|x-amz-signature|signedurl)"
)


def _assert_exact_keys(payload: dict, expected_keys: set[str]) -> None:
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        keys = sorted(payload) if isinstance(payload, dict) else type(payload).__name__
        raise AssertionError(
            f"payload keys must be {sorted(expected_keys)}, got {keys}"
        )


def assert_error_envelope(payload: dict) -> None:
    _assert_exact_keys(payload, ERROR_ENVELOPE_KEYS)
    trace_id = payload["trace_id"]
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise AssertionError("error envelope trace_id must be a non-empty string")


def assert_event_envelope(payload: dict) -> None:
    _assert_exact_keys(payload, EVENT_ENVELOPE_KEYS)
    if not payload["trace_id"]:
        raise AssertionError("event envelope trace_id must be non-empty")


def assert_no_sensitive(text: str) -> None:
    if not isinstance(text, str):
        raise AssertionError("text must be a string")
    for pattern in (SENSITIVE_VALUE_PATTERN, SIGNED_URL_PATTERN):
        match = pattern.search(text)
        if match and "***REDACTED***" not in match.group(0):
            raise AssertionError(f"sensitive value found: {match.group(0)}")


def assert_no_object_storage_leak(response) -> None:
    body = response.content.decode("utf-8", errors="replace").lower()
    for marker in OBJECT_STORAGE_MARKERS:
        if marker in body:
            raise AssertionError(
                f"object storage marker found in response body: {marker}"
            )

    for name, value in response.headers.items():
        header = f"{name}: {value}".lower()
        for marker in OBJECT_STORAGE_MARKERS:
            if marker in header:
                raise AssertionError(
                    f"object storage marker found in response header: {marker}"
                )


class StructuredLogCapture:
    def __init__(self) -> None:
        self._stream = io.StringIO()

    def records(self) -> list[dict]:
        self._stream.seek(0)
        return [json.loads(line) for line in self._stream if line.strip()]

    __call__ = records


@contextmanager
def capture_structured_logs() -> Iterator[StructuredLogCapture]:
    capture = StructuredLogCapture()
    handler = logging.StreamHandler(capture._stream)
    handler.setFormatter(StructuredJsonFormatter())
    loggers = (logging.getLogger(), logging.getLogger("django"))
    original_levels = [(logger, logger.level) for logger in loggers]
    for logger in loggers:
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    try:
        yield capture
    finally:
        for logger, original_level in original_levels:
            logger.removeHandler(handler)
            logger.setLevel(original_level)
        handler.close()
