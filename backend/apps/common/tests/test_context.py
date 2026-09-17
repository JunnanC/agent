from __future__ import annotations

import pytest

from apps.common.context import (
    RequestContext,
    current_action,
    current_context,
    current_request_id,
    current_trace_id,
    current_user_id,
    reset_context,
    set_context,
)


def test_context_round_trip() -> None:
    context = RequestContext("request-id", "trace-id", "1", "action")
    token = set_context(context)

    try:
        assert current_context() is context
        assert current_request_id() == "request-id"
        assert current_trace_id() == "trace-id"
        assert current_user_id() == "1"
        assert current_action() == "action"
    finally:
        reset_context(token)


def test_current_context_requires_active_context() -> None:
    with pytest.raises(RuntimeError, match="not active"):
        current_context()
