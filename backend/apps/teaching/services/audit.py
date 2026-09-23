"""教师端审计封装。

复用 apps.common.audit 的脱敏与检索能力，本模块只负责把请求上下文
（actor、trace、request、幂等键、IP、UA）一次性装配成 AuditRecord。
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.http import HttpRequest

from apps.common.audit import AuditRecord, hash_user_agent, record_audit
from apps.common.context import current_request_id, current_trace_id
from apps.common.errors import INTERNAL_ERROR, ApiError
from apps.common.models import AuditLog
from apps.common.providers import actor_identifier, actor_role

from ..constants import AUDIT_RESULT_SUCCESS, AUDIT_RESULTS


def audit_teaching(
    request: HttpRequest,
    *,
    action: str,
    target_type: str,
    target_id: str,
    result: str = AUDIT_RESULT_SUCCESS,
    reason: str = "",
    before: Any = None,
    after: Any = None,
    assignment_id: str | None = None,
    instance_id: str | None = None,
) -> AuditLog:
    """写入一条教师端审计。

    必须在数据库事务内调用：审计与业务事实同事务（Guideline 03 §5、04 §4），
    业务回滚时审计一并回滚，避免出现"有审计无事实"的记录。
    """

    if not transaction.get_connection().in_atomic_block:
        raise ApiError(INTERNAL_ERROR, message="审计必须与业务事实在同一事务内写入")
    if result not in AUDIT_RESULTS:
        raise ValueError(f"未注册的审计结果: {result}")

    return record_audit(
        AuditRecord(
            actor_user_id=actor_identifier(request),
            actor_role_code=actor_role(request),
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            assignment_id=assignment_id,
            instance_id=instance_id,
            trace_id=current_trace_id(),
            request_id=current_request_id(),
            idempotency_key=request.headers.get("Idempotency-Key"),
            result=result,  # type: ignore[arg-type]
            reason=reason,
            before_json=before,
            after_json=after,
            ip=request.META.get("REMOTE_ADDR", ""),
            user_agent_hash=hash_user_agent(request.headers.get("User-Agent", "")),
        )
    )
