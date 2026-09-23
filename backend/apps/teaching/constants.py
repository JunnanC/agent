"""教师端（教学端 portal）的常量注册表。

本模块只放教师端跨切片共享的字面量，避免事件类型、topic、幂等 scope 与聚合类型
以字符串字面量散落在视图和服务里。新增取值时必须同步更新对应的冻结集合，
这样拼写错误会在导入期就暴露，而不是等运行到那条分支才发现。
"""

from __future__ import annotations

# 教学端 portal，取值来自 apps.common.portal.PORTALS。
TEACHING_PORTAL = "TEACHING"
TEACHING_PORTALS = frozenset({TEACHING_PORTAL})

# 审计结果，取值与 apps.common.audit.AuditRecord.result 的 Literal 保持一致。
AUDIT_RESULT_SUCCESS = "SUCCESS"
AUDIT_RESULT_DENIED = "DENIED"
AUDIT_RESULT_FAILURE = "FAILURE"
AUDIT_RESULTS = frozenset({AUDIT_RESULT_SUCCESS, AUDIT_RESULT_DENIED, AUDIT_RESULT_FAILURE})

# 聚合类型：同时用作审计的 target_type 与 Outbox 的 aggregate_type。
AGGREGATE_TASK = "TASK"
AGGREGATE_REPORT_VERSION = "REPORT_VERSION"
AGGREGATE_MEMBERSHIP = "MEMBERSHIP"

# 事件 topic，与 membership 的 membership.events 并列。
TOPIC_TEACHING_TASK = "teaching.task.events"
TOPIC_TEACHING_REVIEW = "teaching.review.events"

# 事件类型，命名约定 <domain>.<fact>，与 membership.applied 等既有事件同构。
EVENT_TASK_PUBLISHED = "task.published"
EVENT_TASK_WITHDRAWN = "task.withdrawn"
EVENT_REPORT_REVIEWED = "report.reviewed"

# 幂等 scope，命名约定 <domain>.<operation>。
IDEMPOTENCY_SCOPE_TASK_PUBLISH = "teaching.task.publish"
IDEMPOTENCY_SCOPE_TASK_WITHDRAW = "teaching.task.withdraw"
IDEMPOTENCY_SCOPE_REPORT_REVIEW = "teaching.report.review"

# 允许通过 teaching_idempotent 使用的全部 scope。视图里禁止直接写字面量。
IDEMPOTENCY_SCOPES = frozenset(
    {
        IDEMPOTENCY_SCOPE_TASK_PUBLISH,
        IDEMPOTENCY_SCOPE_TASK_WITHDRAW,
        IDEMPOTENCY_SCOPE_REPORT_REVIEW,
    }
)
