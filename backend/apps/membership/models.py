from __future__ import annotations

from typing import ClassVar

from django.db import models


class TeamSettings(models.Model):
    class UnverifiedStartPolicy(models.TextChoices):
        DENIED = "DENIED"
        READ_ONLY = "READ_ONLY"
        ALLOWED = "ALLOWED"

    class ReviewMode(models.TextChoices):
        MANUAL = "MANUAL"
        AUTO = "AUTO"
        COMBINED = "COMBINED"

    id = models.PositiveSmallIntegerField(primary_key=True)
    team_name = models.CharField(max_length=128)
    team_code = models.CharField(max_length=64, unique=True)
    auth_password_enabled = models.BooleanField()
    auth_school_enabled = models.BooleanField()
    auth_enterprise_enabled = models.BooleanField()
    unverified_start_policy = models.CharField(max_length=16, choices=UnverifiedStartPolicy.choices)
    default_report_required = models.BooleanField()
    default_review_mode = models.CharField(max_length=16, choices=ReviewMode.choices)
    default_archive_retention_days = models.PositiveIntegerField()
    default_audit_retention_days = models.PositiveIntegerField()
    default_runtime_log_retention_days = models.PositiveIntegerField()
    updated_by_id = models.BigIntegerField(null=True)
    max_attachment_size_mb = models.PositiveIntegerField()
    allowed_attachment_mime = models.JSONField()
    storage_alert_warn_percent = models.PositiveSmallIntegerField()
    storage_alert_critical_percent = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "team_settings"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(condition=models.Q(id=1), name="team_settings_singleton")
        ]


class TeamMembership(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        ACTIVE = "ACTIVE"
        REJECTED = "REJECTED"
        EXITED = "EXITED"
        REMOVED = "REMOVED"

    class JoinSource(models.TextChoices):
        APPLY = "APPLY"
        DIRECT = "DIRECT"
        IMPORT = "IMPORT"

    id = models.BigAutoField(primary_key=True)
    team = models.ForeignKey(
        TeamSettings,
        on_delete=models.DO_NOTHING,
        db_column="team_id",
        related_name="memberships",
    )
    membership_no = models.CharField(max_length=32, unique=True)
    user_id = models.BigIntegerField(unique=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    join_source = models.CharField(max_length=16, choices=JoinSource.choices)
    previous_status = models.CharField(max_length=16, blank=True, default="")
    requested_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(null=True)
    reviewed_by_id = models.BigIntegerField(null=True)
    reject_reason = models.CharField(max_length=500, blank=True, default="")
    joined_at = models.DateTimeField(null=True)
    exited_at = models.DateTimeField(null=True)
    removed_at = models.DateTimeField(null=True)
    last_block_check_json = models.JSONField(null=True)
    created_by_id = models.BigIntegerField(null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "team_memberships"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["status"], name="idx_membership_status"),
            models.Index(fields=["reviewed_by_id"], name="idx_membership_reviewed_by"),
            models.Index(fields=["team", "status"], name="idx_memberships_team_status"),
        ]
