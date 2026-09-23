from __future__ import annotations

from apps.common.responses import accepted, failure, paginated, success


def test_success_envelope() -> None:
    payload = success({"value": 1}, "request-id")

    assert payload == {
        "data": {"value": 1},
        "meta": {"message": "ok", "request_id": "request-id", "trace_id": ""},
        "error": None,
    }


def test_paginated_envelope() -> None:
    payload = paginated([{"id": 1}], 2, 20, 101, "request-id")

    assert payload["data"] == {
        "items": [{"id": 1}],
        "page": 2,
        "page_size": 20,
        "total": 101,
    }
    assert payload["meta"] == {
        "message": "ok",
        "request_id": "request-id",
        "trace_id": "",
    }
    assert payload["error"] is None


def test_accepted_envelope() -> None:
    payload = accepted("operation-id", "trace-id", "request-id")

    assert payload == {
        "data": {
            "operation_id": "operation-id",
            "status": "ACCEPTED",
        },
        "meta": {
            "message": "ok",
            "request_id": "request-id",
            "trace_id": "trace-id",
        },
        "error": None,
    }


def test_accepted_envelope_with_estimated_records() -> None:
    payload = accepted("operation-id", "trace-id", "request-id", estimated_records=2)

    assert payload["data"]["estimated_records"] == 2


def test_failure_envelope_uses_numeric_code() -> None:
    payload = failure(
        40004, "筛选条件不能为空", "request-id", [{"field": "filters", "issue": "empty"}]
    )

    assert payload["data"] is None
    assert payload["error"]["code"] == 40004
    assert payload["error"]["detail"]["details"] == [{"field": "filters", "issue": "empty"}]
