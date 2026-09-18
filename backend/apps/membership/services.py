from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.http import HttpRequest

from apps.common.audit import AuditRecord, hash_user_agent, record_audit
from apps.common.context import current_request_id, current_trace_id
from apps.common.errors import (
    FORBIDDEN,
    LAST_TEAM_ADMIN_PROTECTED,
    MEMBERSHIP_CHANGE_BLOCKED,
    MEMBERSHIP_PENDING,
    MEMBERSHIP_REQUIRED,
    RESOURCE_NOT_FOUND,
    STATE_CONFLICT,
    ApiError,
)
from apps.common.outbox import OutboxMessage, publish_outbox
from apps.identity.selectors import get_user, visible_users

from .blocking import BlockItem, has_blocking_items
from .constants import (
    AGGREGATE_TYPE_MEMBERSHIP,
    AGGREGATE_TYPE_SESSION,
    EVENT_MEMBERSHIP_ADDED,
    EVENT_MEMBERSHIP_APPLIED,
    EVENT_MEMBERSHIP_APPROVED,
    EVENT_MEMBERSHIP_EXITED,
    EVENT_MEMBERSHIP_REJECTED,
    EVENT_MEMBERSHIP_REMOVED,
    EVENT_SESSION_REVOCATION_REQUESTED,
    JOIN_SOURCE_API_VALUES,
    JOIN_SOURCE_APPLY,
    JOIN_SOURCE_DIRECT,
    MEMBERSHIP_STATUS_ACTIVE,
    MEMBERSHIP_STATUS_PENDING,
    MEMBERSHIP_TOPIC,
    MEMBERSHIP_TRANSITIONS,
    SESSION_TOPIC,
)
from .models import TeamMembership, TeamSettings


def get_team_settings() -> TeamSettings:
    settings = TeamSettings.objects.filter(id=1).first()
    if settings is None:
        raise ApiError(RESOURCE_NOT_FOUND, message="团队配置不存在")
    return settings


def is_active_member(user_id: int) -> bool:
    return TeamMembership.objects.filter(user_id=user_id, status=MEMBERSHIP_STATUS_ACTIVE).exists()


def get_active_membership_id(user_id: int) -> int | None:
    return (
        TeamMembership.objects.filter(user_id=user_id, status=MEMBERSHIP_STATUS_ACTIVE)
        .values_list("id", flat=True)
        .first()
    )


def assert_member_active(user_id: int) -> int:
    membership = TeamMembership.objects.filter(user_id=user_id).only("id", "status").first()
    if membership is None:
        raise ApiError(MEMBERSHIP_REQUIRED)
    if membership.status == MEMBERSHIP_STATUS_PENDING:
        raise ApiError(MEMBERSHIP_PENDING)
    if membership.status != MEMBERSHIP_STATUS_ACTIVE:
        raise ApiError(MEMBERSHIP_REQUIRED, message="成员身份已失效")
    return membership.id


def transition_membership(membership: TeamMembership, action: str) -> str:
    current_status = membership.status or None
    transitions = MEMBERSHIP_TRANSITIONS[action]
    next_status = transitions.get(current_status)
    if next_status is None:
        raise ApiError(
            STATE_CONFLICT,
            message="成员状态不支持该操作",
            details=[{"field": "status", "issue": current_status or "NONE"}],
        )
    membership.previous_status = current_status or ""
    membership.status = next_status
    return next_status


def apply_membership(
    actor: Any, message: str, *, request: HttpRequest | None = None
) -> TeamMembership:
    _require_role(actor, {"USER"})
    now = datetime.now(UTC)
    blocked_error: ApiError | None = None
    with transaction.atomic():
        get_team_settings()
        membership = _locked_membership(actor.id)
        if membership is None:
            membership = _create_membership(
                user_id=actor.id,
                status=MEMBERSHIP_STATUS_PENDING,
                join_source=JOIN_SOURCE_APPLY,
                created_by_id=actor.id,
                now=now,
            )
        else:
            try:
                next_status = transition_membership(membership, "apply")
            except ApiError:
                blocked_error = ApiError(
                    MEMBERSHIP_CHANGE_BLOCKED,
                    message="当前成员状态不允许再次申请",
                    details=[{"field": "status", "issue": membership.status}],
                )
                _record_membership_audit(
                    request,
                    actor,
                    "membership.apply",
                    membership,
                    result="FAILURE",
                    reason=blocked_error.error_message,
                    after={"status": membership.status},
                )
            else:
                membership.requested_at = now
                membership.reviewed_at = None
                membership.reviewed_by_id = None
                membership.reject_reason = ""
                membership.joined_at = None
                membership.exited_at = None
                membership.removed_at = None
                membership.last_block_check_json = None
                membership.created_by_id = actor.id
                membership.updated_at = now
                membership.save(update_fields=_membership_update_fields(next_status))

        if blocked_error is None:
            _publish_membership_event(
                request,
                EVENT_MEMBERSHIP_APPLIED,
                membership,
                {"user_id": actor.id, "message": message},
            )
            _record_membership_audit(
                request,
                actor,
                "membership.apply",
                membership,
                after={"status": membership.status, "message": message},
            )
    if blocked_error is not None:
        raise blocked_error
    return membership


def review_application(
    actor: Any,
    membership_id: int,
    action: str,
    review_note: str,
    *,
    request: HttpRequest | None = None,
) -> TeamMembership:
    _require_role(actor, {"ORG_ADMIN"})
    if action not in {"APPROVE", "REJECT"}:
        raise ApiError(
            STATE_CONFLICT,
            message="审核动作无效",
            details=[{"field": "action", "issue": action}],
        )
    now = datetime.now(UTC)
    with transaction.atomic():
        membership = (
            TeamMembership.objects.select_for_update()
            .filter(id=membership_id, join_source=JOIN_SOURCE_APPLY)
            .first()
        )
        if membership is None:
            raise ApiError(RESOURCE_NOT_FOUND)
        if membership.status != MEMBERSHIP_STATUS_PENDING:
            _raise_after_audit(
                request,
                actor,
                membership,
                "membership.review",
                ApiError(
                    STATE_CONFLICT,
                    message="申请已处理",
                    details=[{"field": "status", "issue": membership.status}],
                ),
            )

        before_status = membership.status
        transition = "approve" if action == "APPROVE" else "reject"
        next_status = transition_membership(membership, transition)
        membership.reviewed_at = now
        membership.reviewed_by_id = actor.id
        membership.updated_at = now
        if action == "REJECT":
            membership.reject_reason = review_note
        if action == "APPROVE":
            membership.joined_at = now
        membership.save(update_fields=_membership_update_fields(next_status, reviewed=True))

        event_type = EVENT_MEMBERSHIP_APPROVED if action == "APPROVE" else EVENT_MEMBERSHIP_REJECTED
        _publish_membership_event(
            request,
            event_type,
            membership,
            {"user_id": membership.user_id, "review_note": review_note},
        )
        _record_membership_audit(
            request,
            actor,
            "membership.review",
            membership,
            before={"status": before_status},
            after={"status": membership.status, "action": action},
        )
    return membership


def direct_add_member(
    actor: Any, username: str, *, request: HttpRequest | None = None
) -> TeamMembership:
    _require_role(actor, {"ORG_ADMIN"})
    user = visible_users().filter(username=username).first()
    if user is None or user.status != "ACTIVE":
        raise ApiError(RESOURCE_NOT_FOUND, message="用户不存在或不可添加")
    now = datetime.now(UTC)
    with transaction.atomic():
        membership = _locked_membership(user.id)
        if membership is not None:
            _raise_after_audit(
                request,
                actor,
                membership,
                "membership.add",
                ApiError(
                    MEMBERSHIP_CHANGE_BLOCKED,
                    message="用户已有成员记录",
                    details=[{"field": "user_id", "issue": str(user.id)}],
                ),
            )
        membership = _create_membership(
            user_id=user.id,
            status=MEMBERSHIP_STATUS_ACTIVE,
            join_source=JOIN_SOURCE_DIRECT,
            created_by_id=actor.id,
            now=now,
            joined_at=now,
            reviewed_by_id=actor.id,
            reviewed_at=now,
        )
        _publish_membership_event(
            request,
            EVENT_MEMBERSHIP_ADDED,
            membership,
            {"user_id": user.id, "username": username},
        )
        _record_membership_audit(
            request,
            actor,
            "membership.add",
            membership,
            after={"status": membership.status, "username": username},
        )
    return membership


def exit_membership(
    actor: Any, reason: str, *, request: HttpRequest | None = None
) -> TeamMembership:
    _require_role(actor, {"USER"})
    return _close_membership(actor, actor.id, "exit", reason, request=request)


def remove_membership(
    actor: Any,
    membership_id: int,
    reason: str,
    *,
    request: HttpRequest | None = None,
) -> TeamMembership:
    _require_role(actor, {"ORG_ADMIN"})
    membership = TeamMembership.objects.filter(id=membership_id).first()
    if membership is None:
        raise ApiError(RESOURCE_NOT_FOUND)
    return _close_membership(actor, membership.user_id, "remove", reason, request=request)


def _close_membership(
    actor: Any,
    user_id: int,
    operation: str,
    reason: str,
    *,
    request: HttpRequest | None = None,
) -> TeamMembership:
    now = datetime.now(UTC)
    blocked_error: ApiError | None = None
    with transaction.atomic():
        team_settings = TeamSettings.objects.select_for_update().get(id=1)
        membership = _locked_membership(user_id)
        if membership is None:
            raise ApiError(RESOURCE_NOT_FOUND)

        if operation == "remove":
            _protect_last_team_admin(membership)

        blockers = has_blocking_items(user_id, operation=operation)
        if blockers:
            membership.last_block_check_json = [item.as_dict() for item in blockers]
            membership.updated_at = now
            membership.save(update_fields=["last_block_check_json", "updated_at"])
            blocked_error = ApiError(
                MEMBERSHIP_CHANGE_BLOCKED,
                message="存在阻断事项，成员变更被阻止",
                details=[item.as_dict() for item in blockers],
            )
            _record_membership_audit(
                request,
                actor,
                f"membership.{operation}",
                membership,
                result="FAILURE",
                reason="blocking items",
                after={"blocking_items": membership.last_block_check_json},
            )
        else:
            before_status = membership.status
            next_status = transition_membership(membership, operation)
            membership.last_block_check_json = []
            membership.updated_at = now
            if operation == "exit":
                membership.exited_at = now
            else:
                membership.removed_at = now
            membership.save(update_fields=_membership_update_fields(next_status, closed=True))

            event_type = (
                EVENT_MEMBERSHIP_EXITED if operation == "exit" else EVENT_MEMBERSHIP_REMOVED
            )
            _publish_membership_event(
                request, event_type, membership, {"user_id": user_id, "reason": reason}
            )
            _publish_session_revocation(request, membership.user_id)
            _record_membership_audit(
                request,
                actor,
                f"membership.{operation}",
                membership,
                before={"status": before_status},
                after={"status": membership.status, "reason": reason},
            )
        _ = team_settings
    if blocked_error is not None:
        raise blocked_error
    return membership


def _protect_last_team_admin(membership: TeamMembership) -> None:
    user = get_user(membership.user_id)
    if user is None or user.role_code != "ORG_ADMIN":
        return
    active_user_ids = list(
        TeamMembership.objects.filter(status=MEMBERSHIP_STATUS_ACTIVE).values_list(
            "user_id", flat=True
        )
    )
    active_admins = visible_users().filter(
        id__in=active_user_ids,
        role__role_code="ORG_ADMIN",
        status="ACTIVE",
        deleted_at__isnull=True,
    )
    if active_admins.count() <= 1:
        # CONFLICT-C13: 接口文档写 40303，但权威错误字典登记为 40905。
        raise ApiError(LAST_TEAM_ADMIN_PROTECTED)


def _create_membership(
    *,
    user_id: int,
    status: str,
    join_source: str,
    created_by_id: int,
    now: datetime,
    joined_at: datetime | None = None,
    reviewed_by_id: int | None = None,
    reviewed_at: datetime | None = None,
) -> TeamMembership:
    try:
        return TeamMembership.objects.create(
            team_id=1,
            membership_no=_membership_no(),
            user_id=user_id,
            status=status,
            join_source=join_source,
            previous_status="",
            requested_at=now,
            reviewed_at=reviewed_at,
            reviewed_by_id=reviewed_by_id,
            joined_at=joined_at,
            created_by_id=created_by_id,
            created_at=now,
            updated_at=now,
        )
    except IntegrityError as exc:
        raise ApiError(
            MEMBERSHIP_CHANGE_BLOCKED,
            message="成员记录创建冲突",
            details=[{"field": "user_id", "issue": str(user_id)}],
        ) from exc


def _locked_membership(user_id: int) -> TeamMembership | None:
    return (
        TeamMembership.objects.select_for_update()
        .filter(user_id=user_id)
        .select_related("team")
        .first()
    )


def _membership_no() -> str:
    return f"TM{datetime.now(UTC).year}{uuid.uuid4().hex[:16].upper()}"


def _membership_update_fields(
    next_status: str, *, reviewed: bool = False, closed: bool = False
) -> list[str]:
    fields = ["status", "previous_status", "updated_at"]
    if next_status == MEMBERSHIP_STATUS_PENDING:
        fields.extend(
            [
                "requested_at",
                "reviewed_at",
                "reviewed_by_id",
                "reject_reason",
                "joined_at",
                "exited_at",
                "removed_at",
                "last_block_check_json",
                "created_by_id",
            ]
        )
    if reviewed:
        fields.extend(["reviewed_at", "reviewed_by_id", "reject_reason", "joined_at"])
    if closed:
        fields.extend(["last_block_check_json", "exited_at", "removed_at"])
    return list(dict.fromkeys(fields))


def _require_role(actor: Any, roles: set[str]) -> None:
    role_code = getattr(actor, "role_code", None)
    if role_code not in roles:
        raise ApiError(FORBIDDEN)


def _publish_membership_event(
    request: HttpRequest | None,
    event_type: str,
    membership: TeamMembership,
    payload: dict[str, Any],
) -> None:
    publish_outbox(
        OutboxMessage(
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            trace_id=_trace_id(),
            aggregate_type=AGGREGATE_TYPE_MEMBERSHIP,
            aggregate_id=str(membership.id),
            topic=MEMBERSHIP_TOPIC,
            extra_payload={
                "membership_id": membership.id,
                "user_id": membership.user_id,
                "status": membership.status,
                "join_source": JOIN_SOURCE_API_VALUES[membership.join_source],
                **payload,
            },
        )
    )


def _publish_session_revocation(request: HttpRequest | None, user_id: int) -> None:
    publish_outbox(
        OutboxMessage(
            event_type=EVENT_SESSION_REVOCATION_REQUESTED,
            occurred_at=datetime.now(UTC),
            trace_id=_trace_id(),
            aggregate_type=AGGREGATE_TYPE_SESSION,
            aggregate_id=str(user_id),
            topic=SESSION_TOPIC,
            extra_payload={"user_id": user_id},
        )
    )


def _record_membership_audit(
    request: HttpRequest | None,
    actor: Any,
    action: str,
    membership: TeamMembership,
    *,
    result: str = "SUCCESS",
    reason: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    record_audit(
        AuditRecord(
            actor_user_id=str(actor.id),
            actor_role_code=actor.role_code,
            action=action,
            target_type="MEMBERSHIP",
            target_id=str(membership.id),
            assignment_id=None,
            instance_id=None,
            trace_id=_trace_id(),
            request_id=_request_id(),
            idempotency_key=_idempotency_key(request),
            result=result,  # type: ignore[arg-type]
            reason=reason,
            before_json=before,
            after_json=after,
            ip=_ip(request),
            user_agent_hash=hash_user_agent(_user_agent(request)),
        )
    )


def _raise_after_audit(
    request: HttpRequest | None,
    actor: Any,
    membership: TeamMembership,
    action: str,
    error: ApiError,
) -> None:
    _record_membership_audit(
        request,
        actor,
        action,
        membership,
        result="FAILURE",
        reason=error.error_message,
        after={"status": membership.status},
    )
    raise error


def _request_id() -> str:
    return current_request_id() or str(uuid.uuid4())


def _trace_id() -> str:
    return current_trace_id() or str(uuid.uuid4())


def _idempotency_key(request: HttpRequest | None) -> str | None:
    return request.headers.get("Idempotency-Key") if request is not None else None


def _ip(request: HttpRequest | None) -> str:
    return request.META.get("REMOTE_ADDR", "") if request is not None else ""


def _user_agent(request: HttpRequest | None) -> str:
    return request.headers.get("User-Agent", "") if request is not None else ""


def active_members() -> QuerySet[TeamMembership]:
    return TeamMembership.objects.filter(status=MEMBERSHIP_STATUS_ACTIVE)


def membership_block_items(user_id: int, *, operation: str = "exit") -> list[BlockItem]:
    return has_blocking_items(user_id, operation=operation)
