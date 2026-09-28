from __future__ import annotations

from typing import Any, ClassVar

from django.db import models

from apps.runtime.enums import CompensationStatus

from .append_only import AppendOnlyViolation


class OutboxEvent(models.Model):
    """Append-only business event payload with mutable delivery projection."""

    id = models.BigAutoField(primary_key=True)
    event_id = models.CharField(max_length=36, unique=True)
    event_type = models.CharField(max_length=64)
    aggregate_type = models.CharField(max_length=64)
    aggregate_id = models.CharField(max_length=64)
    assignment_id = models.CharField(max_length=64, null=True, blank=True)
    instance_id = models.CharField(max_length=64, null=True, blank=True)
    topic = models.CharField(max_length=128)
    payload_json = models.JSONField()
    status = models.CharField(max_length=16)
    attempt_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField()
    published_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    trace_id = models.CharField(max_length=128)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "outbox_events"


class AuditLog(models.Model):
    """Immutable audit fact; corrections are represented by new facts."""

    id = models.BigAutoField(primary_key=True)
    actor_user_id = models.CharField(max_length=64, null=True, blank=True)
    actor_role_code = models.CharField(max_length=32, null=True, blank=True)
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=32)
    target_id = models.CharField(max_length=64)
    assignment_id = models.CharField(max_length=64, null=True, blank=True)
    instance_id = models.CharField(max_length=64, null=True, blank=True)
    trace_id = models.CharField(max_length=128)
    request_id = models.CharField(max_length=36)
    idempotency_key = models.CharField(max_length=64, null=True, blank=True)
    result = models.CharField(max_length=8)
    reason = models.TextField(blank=True, default="")
    before_json = models.JSONField(null=True, blank=True)
    after_json = models.JSONField(null=True, blank=True)
    ip = models.CharField(max_length=64, blank=True, default="")
    user_agent_hash = models.CharField(max_length=64, null=True, blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "audit_logs"


class ObjectAsset(models.Model):
    """Metadata for one object whose content resides in object storage."""

    class Purpose(models.TextChoices):
        REPORT_ATTACHMENT = "REPORT_ATTACHMENT"
        WORKSPACE_SNAPSHOT = "WORKSPACE_SNAPSHOT"
        ARCHIVE_PACKAGE = "ARCHIVE_PACKAGE"
        AGENT_TRANSCRIPT = "AGENT_TRANSCRIPT"
        TEMPLATE_MATERIAL = "TEMPLATE_MATERIAL"
        IDENTITY_DOCUMENT = "IDENTITY_DOCUMENT"

    class ScanStatus(models.TextChoices):
        PENDING = "PENDING"
        CLEAN = "CLEAN"
        INFECTED = "INFECTED"
        FAILED = "FAILED"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        PURGED = "PURGED"

    id = models.BigAutoField(primary_key=True)
    public_id = models.CharField(max_length=26, unique=True, db_collation="ascii_bin")
    bucket = models.CharField(max_length=128)
    object_key = models.CharField(max_length=512)
    byte_size = models.PositiveBigIntegerField()
    content_type = models.CharField(max_length=128)
    sha256_digest = models.CharField(max_length=64, db_collation="ascii_bin")
    owner_user_id = models.BigIntegerField()
    # Cross-context reference to courses; services and reconciliation enforce consistency.
    owner_course_id = models.BigIntegerField(null=True, blank=True)
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    scan_status = models.CharField(
        max_length=16, choices=ScanStatus.choices, default=ScanStatus.PENDING
    )
    scanned_at = models.DateTimeField(null=True, blank=True)
    retention_until = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.PositiveIntegerField(default=1)

    class Meta:
        managed = False
        db_table = "core_object_asset"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["bucket", "object_key"],
                name="uniq_core_object_asset_bucket_key",
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["owner_user_id", "purpose", "status"],
                name="idx_core_asset_owner_status",
            ),
            models.Index(
                fields=["owner_course_id", "purpose"],
                name="idx_core_asset_course_purpose",
            ),
            models.Index(
                fields=["status", "retention_until"],
                name="idx_core_asset_retention",
            ),
            models.Index(
                fields=["scan_status", "created_at"],
                name="idx_core_asset_scan_created",
            ),
        ]


class FailureRecord(models.Model):
    """Structured, append-only failure fact for one resource."""

    id = models.BigAutoField(primary_key=True)
    failure_code = models.CharField(max_length=64)
    stage = models.CharField(max_length=32, null=True, blank=True)
    resource_type = models.CharField(max_length=64)
    resource_public_id = models.CharField(max_length=26, db_collation="ascii_bin")
    previous_status = models.CharField(max_length=32, null=True, blank=True)
    retryable = models.BooleanField(default=False)
    detail_masked = models.CharField(max_length=512, null=True, blank=True)
    trace_id = models.CharField(max_length=32, db_collation="ascii_bin")
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "core_failure_record"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["resource_type", "resource_public_id", "id"],
                name="idx_core_failure_resource",
            ),
            models.Index(
                fields=["failure_code", "created_at"],
                name="idx_core_failure_code_created",
            ),
            models.Index(fields=["trace_id"], name="idx_core_failure_record_trace"),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            raise AppendOnlyViolation("failure records cannot be updated")
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    def delete(self, *args: Any, **kwargs: Any) -> None:
        raise AppendOnlyViolation("failure records cannot be deleted")


class CompensationTask(models.Model):
    """Versioned compensation task with an operator-visible status."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.CharField(max_length=26, unique=True, db_collation="ascii_bin")
    compensation_type = models.CharField(max_length=64)
    target_type = models.CharField(max_length=64)
    target_public_id = models.CharField(max_length=26, db_collation="ascii_bin")
    status = models.CharField(
        max_length=16,
        choices=[
            (CompensationStatus.PENDING.value, CompensationStatus.PENDING.name),
            (CompensationStatus.RUNNING.value, CompensationStatus.RUNNING.name),
            (CompensationStatus.SUCCEEDED.value, CompensationStatus.SUCCEEDED.name),
            (CompensationStatus.DEAD.value, CompensationStatus.DEAD.name),
        ],
        default=CompensationStatus.PENDING,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_error_masked = models.CharField(max_length=512, null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.PositiveIntegerField(default=1)

    class Meta:
        managed = False
        db_table = "core_compensation_task"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["status", "next_run_at"],
                name="idx_core_comp_task_status_next",
            ),
            models.Index(
                fields=["target_type", "target_public_id"],
                name="idx_core_comp_task_target",
            ),
        ]


class ObjectPurgeLog(models.Model):
    """Append-only fact recorded when an object asset is purged."""

    class OperatorType(models.TextChoices):
        SYSTEM = "SYSTEM"
        ADMIN = "ADMIN"

    id = models.BigAutoField(primary_key=True)
    asset = models.ForeignKey(
        ObjectAsset,
        on_delete=models.RESTRICT,
        db_column="asset_id",
    )
    purge_reason = models.CharField(max_length=64)
    reference_check_json = models.JSONField(null=True, blank=True)
    object_removed_at = models.DateTimeField(null=True, blank=True)
    operator_type = models.CharField(max_length=16, choices=OperatorType.choices)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "core_object_purge_log"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["asset", "id"], name="idx_core_purge_log_asset")
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            raise AppendOnlyViolation("object purge logs cannot be updated")
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    def delete(self, *args: Any, **kwargs: Any) -> None:
        raise AppendOnlyViolation("object purge logs cannot be deleted")
