from __future__ import annotations

import pytest

from apps.membership.blocking import (
    BlockItem,
    blocking_statuses,
    has_blocking_items,
)


def test_exit_and_remove_blocking_statuses_are_distinct() -> None:
    assert "ASSIGNED" in blocking_statuses("exit")
    assert "UNDER_REVIEW" in blocking_statuses("exit")
    assert "ASSIGNED" not in blocking_statuses("remove")
    assert "SUBMITTED" in blocking_statuses("remove")


def test_invalid_operation_is_rejected() -> None:
    with pytest.raises(ValueError):
        has_blocking_items(1, operation="invalid")


def test_block_item_serializes_without_sensitive_data() -> None:
    item = BlockItem("unfinished_assignment", "1", "RUNNING", "实验未完成")

    assert item.as_dict() == {
        "type": "unfinished_assignment",
        "assignment_id": "1",
        "status": "RUNNING",
        "reason": "实验未完成",
    }
