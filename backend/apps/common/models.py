from __future__ import annotations

from django.db import models


class OutboxEvent(models.Model):
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
