from __future__ import annotations

import json

from apps.common.context import RequestContext, reset_context, set_context
from apps.common.errors import ERROR_CODES, ERRORS_BY_CODE, ApiError, drf_exception_handler


def test_error_codes_are_unique() -> None:
    errors = list(ERROR_CODES.values())

    assert len({error.code for error in errors}) == len(errors)
    assert len(ERRORS_BY_CODE) == len(errors)


def test_error_codes_have_http_status() -> None:
    for error in ERROR_CODES.values():
        assert 400 <= error.http_status <= 599
        assert error.symbol
        assert error.message


def test_error_response_uses_numeric_code() -> None:
    token = set_context(RequestContext("request-id", "trace-id", "1", "test"))
    try:
        response = drf_exception_handler(ApiError(ERRORS_BY_CODE[40004]), {})
        payload = json.loads(response.content)
    finally:
        reset_context(token)

    assert response.status_code == 400
    assert payload["code"] == 40004
    assert payload["request_id"] == "request-id"


def test_unknown_exception_returns_internal_error() -> None:
    token = set_context(RequestContext("request-id", "trace-id", "1", "test"))
    try:
        response = drf_exception_handler(RuntimeError("secret-token"), {})
        payload = json.loads(response.content)
    finally:
        reset_context(token)

    assert response.status_code == 500
    assert payload["code"] == 50001
    assert "secret-token" not in response.content.decode()
