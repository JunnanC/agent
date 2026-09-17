from __future__ import annotations

from apps.common.responses import accepted, failure, paginated, success


def test_success_envelope() -> None:
    payload = success({"value": 1}, "request-id")

    assert payload == {
        "code": 0,
        "message": "ok",
        "data": {"value": 1},
        "request_id": "request-id",
    }


def test_paginated_envelope() -> None:
    payload = paginated([{"id": 1}], 2, 20, 101, "request-id")

    assert payload["code"] == 0
    assert payload["data"] == {
        "items": [{"id": 1}],
        "page": 2,
        "page_size": 20,
        "total": 101,
    }


def test_accepted_envelope() -> None:
    payload = accepted("operation-id", "trace-id", "request-id")

    assert payload == {
        "code": 0,
        "message": "accepted",
        "data": {
            "operation_id": "operation-id",
            "trace_id": "trace-id",
            "status": "ACCEPTED",
        },
        "request_id": "request-id",
    }


def test_accepted_envelope_with_estimated_records() -> None:
    payload = accepted("operation-id", "trace-id", "request-id", estimated_records=2)

    assert payload["data"]["estimated_records"] == 2


def test_failure_envelope_uses_numeric_code() -> None:
    payload = failure(
        40004, "筛选条件不能为空", "request-id", [{"field": "filters", "issue": "empty"}]
    )

    assert payload["code"] == 40004
    assert payload["data"]["details"] == [{"field": "filters", "issue": "empty"}]
