from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any

from django.contrib.auth.hashers import make_password
from django.db import transaction

from apps.common.errors import INVALID_ROLE, POLICY_REJECTED, STATE_CONFLICT, ApiError
from apps.common.outbox import OutboxMessage, publish_outbox

from ..models import User, UserQuota
from ..selectors import get_builtin_role, get_user

DEFAULT_QUOTA = {
    "max_instances": 5,
    "max_cpu_millicores": 4000,
    "max_memory_mb": 8192,
    "max_disk_mb": 51200,
    "max_vm_count": 2,
    "max_gpu_count": 0,
}


def create_user(actor_id: int, data: dict[str, Any]) -> User:
    now = datetime.now(UTC)
    role = get_builtin_role(data["role_id"])
    if role is None:
        raise ApiError(INVALID_ROLE)
    with transaction.atomic():
        if User.objects.filter(username=data["username"], deleted_at__isnull=True).exists():
            raise ApiError(STATE_CONFLICT, message="用户名已存在")
        if User.objects.filter(email=data["email"], deleted_at__isnull=True).exists():
            raise ApiError(STATE_CONFLICT, message="邮箱已存在")
        if (
            data.get("phone")
            and User.objects.filter(phone=data["phone"], deleted_at__isnull=True).exists()
        ):
            raise ApiError(STATE_CONFLICT, message="手机号已存在")
        user = User.objects.create(
            username=data["username"],
            email=data["email"],
            phone=data.get("phone") or None,
            password_hash=make_password(data["password"]),
            nickname=data.get("username", ""),
            role=role,
            status="ACTIVE",
            auth_mode="PASSWORD",
            created_by_id=actor_id,
            created_at=now,
            updated_at=now,
        )
        UserQuota.objects.create(user=user, created_at=now, updated_at=now, **DEFAULT_QUOTA)
        if data.get("send_welcome", True):
            publish_outbox(_message("identity.user.created", user, "user.created"))
        return user


def update_user(actor: User, user_id: int, data: dict[str, Any]) -> User:
    user = get_user(user_id)
    if user is None:
        from apps.common.errors import RESOURCE_NOT_FOUND

        raise ApiError(RESOURCE_NOT_FOUND)
    role = get_builtin_role(data["role_id"]) if data.get("role_id") else user.role
    if role is None:
        raise ApiError(INVALID_ROLE)
    status = data.get("status", user.status)
    if user.id == actor.id and (status == "DISABLED" or role.role_code != "SYSTEM_ADMIN"):
        raise ApiError(STATE_CONFLICT, message="不可禁用或降级自身账号")
    now = datetime.now(UTC)
    with transaction.atomic():
        user.status = status
        user.role = role
        user.updated_at = now
        user.save(update_fields=["role", "status", "updated_at"])
        if status == "DISABLED":
            publish_outbox(_message("identity.user.disabled", user, "user.disabled"))
            publish_outbox(_message("workspace.session.revoked", user, "workspace.session.revoked"))
            publish_outbox(_message("notification.revoked", user, "notification.revoked"))
    return user


def parse_import_csv(content: bytes) -> list[dict[str, str]]:
    required = {"username", "password", "email", "role_id"}
    try:
        text = content.decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows or not required.issubset(rows[0]):
            raise ValueError
        return rows
    except (UnicodeDecodeError, ValueError) as exc:
        raise ApiError(POLICY_REJECTED, message="CSV格式错误或缺列") from exc


def _message(event_type: str, user: User, topic: str) -> OutboxMessage:
    return OutboxMessage(
        event_type=event_type,
        occurred_at=datetime.now(UTC),
        trace_id="",
        aggregate_type="USER",
        aggregate_id=str(user.id),
        topic=topic,
        extra_payload={"user_id": user.id, "username": user.username},
    )
