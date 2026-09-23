from apps.core.response.schema import accepted, error, paginated, success


def test_success_and_failure_share_one_top_level_shape() -> None:
    success_payload = success({"value": 1}, request_id="request-id", trace_id="trace-id")
    error_payload = error(40001, "请求参数无效", request_id="request-id", trace_id="trace-id")

    assert set(success_payload) == {"data", "meta", "error"}
    assert set(error_payload) == {"data", "meta", "error"}
    assert success_payload["error"] is None
    assert error_payload["data"] is None


def test_paginated_data_contains_stable_page_contract() -> None:
    payload = paginated(
        [{"id": 1}],
        page=2,
        page_size=20,
        total=41,
        request_id="request-id",
        trace_id="trace-id",
    )

    assert payload["data"] == {
        "items": [{"id": 1}],
        "page": 2,
        "page_size": 20,
        "total": 41,
    }
    assert payload["meta"]["request_id"] == "request-id"
    assert payload["meta"]["trace_id"] == "trace-id"


def test_accepted_keeps_operation_data_in_data_and_trace_in_meta() -> None:
    payload = accepted(
        {"operation_id": "operation-id", "status": "ACCEPTED"},
        request_id="request-id",
        trace_id="trace-id",
    )

    assert payload["data"]["operation_id"] == "operation-id"
    assert payload["meta"]["trace_id"] == "trace-id"
    assert payload["error"] is None
