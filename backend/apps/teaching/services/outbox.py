"""教师端 Outbox 封装。

复用 apps.common.outbox.publish_outbox（必须与业务事实同事务写入）。
本模块在此之上补一层更明确的错误提示，便于定位"忘记放进 teaching_write()"的调用点。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from django.db import transaction

from apps.common.context import current_trace_id
from apps.common.errors import INTERNAL_ERROR, ApiError
from apps.common.models import OutboxEvent
from apps.common.outbox import OutboxMessage, publish_outbox


def publish_teaching_event(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    topic: str,
    payload: dict[str, Any] | None = None,
    assignment_id: str | None = None,
    instance_id: str | None = None,
) -> OutboxEvent:
    """登记一条教师端领域事件。

    payload 只放不透明 ID、状态与业务必要的非敏感字段；敏感字段的脱敏由
    publish_outbox 统一处理，本模块不重复实现。
    """

    if not transaction.get_connection().in_atomic_block:
        raise ApiError(
            INTERNAL_ERROR,
            message="教师端 Outbox 事件必须在 teaching_write() 事务内发布",
        )

    return publish_outbox(
        OutboxMessage(
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            trace_id=current_trace_id(),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            topic=topic,
            assignment_id=assignment_id,
            instance_id=instance_id,
            extra_payload=payload,
        )
    )
