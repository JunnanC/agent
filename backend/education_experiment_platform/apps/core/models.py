"""core 拥有的共享事实表（doc 02 §六）。

core 只承载与业务无关的横切事实：Outbox、审计、请求幂等。它不导入任何业务 app，
业务侧通过显式传参（opaque ID、事件名、载荷）使用这些能力。

这些表是 AppendOnly（doc 07 §二）：生产数据库账号只具 ``SELECT``/``INSERT``，
修正历史靠追加新事实而不是 UPDATE/DELETE。
"""

from __future__ import annotations

from django.db import models


class OutboxEvent(models.Model):
    """业务事务内写入的不可变事件（doc 03 §二）。

    ``payload`` 只允许放 opaque ID、状态、必要摘要和 trace_id；
    禁止 Session、工作区票据、签名 URL、证件原值（doc 01 §十）。
    """

    class Meta:
        db_table = "core_outbox_event"
        indexes = (
            models.Index(fields=("created_at",), name="core_outbox_created_idx"),
            models.Index(fields=("aggregate_type", "aggregate_id"), name="core_outbox_agg_idx"),
        )

    id = models.BigAutoField(primary_key=True)
    event_name = models.CharField(max_length=64)
    aggregate_type = models.CharField(max_length=32)
    # 聚合标识是 opaque ID / public_id，不是数据库自增主键：事件表不持有业务 FK，
    # 避免业务表结构变化反向影响已投递的历史事件。
    aggregate_id = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    trace_id = models.CharField(max_length=32, blank=True, default="")
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.event_name}:{self.aggregate_type}:{self.aggregate_id}"


class OutboxDelivery(models.Model):
    """投递状态投影；Redis Stream 丢失后从这里恢复（doc 03 §二）。

    与 ``OutboxEvent`` 分成两张表，是为了让「事件事实」保持不可变，
    而重试次数、下次投递时间这类**可变**状态只更新投影表。
    """

    STATUS_PENDING = "PENDING"
    STATUS_DELIVERED = "DELIVERED"
    STATUS_FAILED = "FAILED"
    STATUS_DEAD = "DEAD"

    class Meta:
        db_table = "core_outbox_delivery"
        constraints = (
            models.UniqueConstraint(fields=("event",), name="core_outbox_delivery_event_uniq"),
        )
        indexes = (models.Index(fields=("status", "next_attempt_at"), name="core_outbox_due_idx"),)

    id = models.BigAutoField(primary_key=True)
    # RESTRICT 而不是 CASCADE：投递记录不允许因为事件被删而消失（业务不物理删除）。
    event = models.ForeignKey(
        OutboxEvent, on_delete=models.RESTRICT, related_name="deliveries", db_index=True
    )
    status = models.CharField(max_length=16, default=STATUS_PENDING)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    delivered_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=512, blank=True, default="")

    def __str__(self) -> str:
        return f"delivery({self.event_id})={self.status}"


class AuditLog(models.Model):
    """全局审计事实（doc 05 §六）。

    只记录**脱敏后**的前后值；``before_masked``/``after_masked`` 由调用方保证已脱敏，
    ``record_audit`` 会再按敏感键名递归兜底一次。
    """

    class Meta:
        db_table = "core_audit_log"
        indexes = (
            models.Index(fields=("created_at",), name="core_audit_created_idx"),
            models.Index(fields=("target_type", "target_id"), name="core_audit_target_idx"),
            models.Index(fields=("course_ref", "created_at"), name="core_audit_course_idx"),
            models.Index(fields=("actor_ref", "created_at"), name="core_audit_actor_idx"),
        )

    id = models.BigAutoField(primary_key=True)
    actor_ref = models.CharField(max_length=26, db_index=True)
    actor_portal = models.CharField(max_length=16)
    # 资格快照：撤销教师资格后仍要能解释历史操作当时的权限来源。
    actor_qualification = models.CharField(max_length=32, blank=True, default="")
    action = models.CharField(max_length=64)
    course_ref = models.CharField(max_length=26, blank=True, default="")
    target_type = models.CharField(max_length=32)
    target_id = models.CharField(max_length=64)
    before_masked = models.JSONField(null=True, blank=True)
    after_masked = models.JSONField(null=True, blank=True)
    result = models.CharField(max_length=16)
    error_code = models.CharField(max_length=64, blank=True, default="")
    client_ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent_summary = models.CharField(max_length=128, blank=True, default="")
    trace_id = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.action}:{self.target_type}:{self.target_id}"


class IdempotencyRecord(models.Model):
    """请求幂等记录（doc 02 §七）。

    唯一键是 (actor_ref, endpoint, key)：同一个幂等键在不同 endpoint 上互不影响，
    但同一个 endpoint 上重复使用同一个键而请求摘要不同，返回 ``IDEMPOTENCY_KEY_REUSED``。
    """

    class Meta:
        db_table = "core_idempotency_record"
        constraints = (
            models.UniqueConstraint(
                fields=("actor_ref", "endpoint", "key"), name="core_idempotency_scope_uniq"
            ),
        )
        indexes = (models.Index(fields=("expires_at",), name="core_idempotency_expires_idx"),)

    id = models.BigAutoField(primary_key=True)
    key = models.CharField(max_length=36)
    actor_ref = models.CharField(max_length=26)
    endpoint = models.CharField(max_length=120)
    request_digest = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField(default=200)
    response_body = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self) -> str:
        return f"{self.endpoint}:{self.key}"
