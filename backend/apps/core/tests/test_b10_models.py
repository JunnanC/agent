from __future__ import annotations

import pytest

from apps.core.append_only import AppendOnlyViolation
from apps.core.models import CompensationTask, FailureRecord, ObjectAsset, ObjectPurgeLog
from apps.runtime.enums import CompensationStatus


def make_object_asset() -> ObjectAsset:
    return ObjectAsset(
        public_id="01JAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        bucket="general",
        object_key="assignment/report.pdf",
        byte_size=1024,
        content_type="application/pdf",
        sha256_digest="a" * 64,
        owner_user_id=1,
        purpose=ObjectAsset.Purpose.REPORT_ATTACHMENT,
        created_at="2026-09-28T00:43:00Z",
    )


def make_compensation_task() -> CompensationTask:
    return CompensationTask(
        public_id="01JBBBBBBBBBBBBBBBBBBBBBBB",
        compensation_type="PURGE_OBJECT",
        target_type="OBJECT_ASSET",
        target_public_id="01JAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        created_at="2026-09-28T00:43:00Z",
    )


def test_object_asset_defaults_and_metadata() -> None:
    asset = make_object_asset()

    assert asset.scan_status == ObjectAsset.ScanStatus.PENDING
    assert asset.status == ObjectAsset.Status.ACTIVE
    assert asset.row_version == 1
    assert ObjectAsset._meta.db_table == "core_object_asset"
    assert ObjectAsset._meta.managed is False


def test_compensation_task_defaults_and_metadata() -> None:
    task = make_compensation_task()

    assert task.status == CompensationStatus.PENDING
    assert task.attempt_count == 0
    assert task.row_version == 1
    assert CompensationTask._meta.db_table == "core_compensation_task"
    assert CompensationTask._meta.get_field("status").choices == [
        ("PENDING", "PENDING"),
        ("RUNNING", "RUNNING"),
        ("SUCCEEDED", "SUCCEEDED"),
        ("DEAD", "DEAD"),
    ]
    assert CompensationStatus.DEAD.value == "DEAD"
    assert CompensationTask._meta.managed is False


def test_failure_record_is_append_only() -> None:
    record = FailureRecord(
        failure_code="TASK_FAILED",
        resource_type="TASK",
        resource_public_id="01JCCCCCCCCCCCCCCCCCCCCCCC",
        trace_id="0" * 32,
        created_at="2026-09-28T00:43:00Z",
    )
    record.pk = 1

    with pytest.raises(AppendOnlyViolation, match="cannot be updated"):
        record.save()

    with pytest.raises(AppendOnlyViolation, match="cannot be deleted"):
        record.delete()


def test_object_purge_log_is_append_only() -> None:
    log = ObjectPurgeLog(
        asset=make_object_asset(),
        purge_reason="RETENTION_EXPIRED",
        operator_type=ObjectPurgeLog.OperatorType.SYSTEM,
        created_at="2026-09-28T00:43:00Z",
    )
    log.pk = 1

    with pytest.raises(AppendOnlyViolation, match="cannot be updated"):
        log.save()

    with pytest.raises(AppendOnlyViolation, match="cannot be deleted"):
        log.delete()


def test_append_only_models_have_no_versioning_columns() -> None:
    assert {field.name for field in FailureRecord._meta.fields}.isdisjoint(
        {"updated_at", "row_version"}
    )
    assert {field.name for field in ObjectPurgeLog._meta.fields}.isdisjoint(
        {"updated_at", "row_version"}
    )
