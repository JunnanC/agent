from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from apps.common.audit import AuditRecord, hash_user_agent, record_audit
from apps.common.context import current_request_id, current_trace_id


def audit_identity(
    request: HttpRequest,
    *,
    action: str,
    target_type: str,
    target_id: str,
    result: str,
    reason: str = "",
    before: Any = None,
    after: Any = None,
) -> None:
    record_audit(
        AuditRecord(
            actor_user_id=str(getattr(request, "identity_user_id", "") or "") or None,
            actor_role_code=str(getattr(request, "identity_role_code", "") or "") or None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            assignment_id=None,
            instance_id=None,
            trace_id=current_trace_id(),
            request_id=current_request_id(),
            idempotency_key=request.headers.get("Idempotency-Key"),
            result=result,
            reason=reason,
            before_json=before,
            after_json=after,
            ip=request.META.get("REMOTE_ADDR", ""),
            user_agent_hash=hash_user_agent(request.headers.get("User-Agent", "")),
        )
    )
