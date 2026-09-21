from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from django.contrib.auth.hashers import make_password
from django.db import connection

from apps.common.models import AuditLog, OutboxEvent
from apps.identity.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserQuota,
    UserVerification,
)


def _drop_tables() -> None:
    tables = (
        "user_verifications",
        "user_quotas",
        "users",
        "role_permissions",
        "permissions",
        "roles",
        "audit_logs",
        "outbox_events",
    )
    with connection.cursor() as cursor:
        for table in tables:
            cursor.execute(f'DROP TABLE IF EXISTS "{table}"')


def _create_tables() -> None:
    with connection.schema_editor() as editor:
        for model in (
            Role,
            Permission,
            RolePermission,
            User,
            UserVerification,
            UserQuota,
            AuditLog,
            OutboxEvent,
        ):
            editor.create_model(model)


@pytest.fixture
def identity_tables(transactional_db: None) -> Iterator[None]:
    _drop_tables()
    _create_tables()
    try:
        yield
    finally:
        _drop_tables()


@pytest.fixture
def roles(identity_tables: None) -> dict[str, Role]:
    now = datetime.now(UTC)
    values = {
        role_code: Role.objects.create(
            role_code=role_code,
            role_name=role_code,
            is_system=True,
            created_at=now,
            updated_at=now,
        )
        for role_code in ("SYSTEM_ADMIN", "ORG_ADMIN", "ORG_SUB_ADMIN", "USER")
    }
    return values


def make_user(
    roles: dict[str, Role],
    *,
    username: str = "user",
    role_code: str = "USER",
    status: str = "ACTIVE",
    password: str = "Password123",
) -> User:
    now = datetime.now(UTC)
    user = User.objects.create(
        username=username,
        email=f"{username}@example.com",
        phone=f"+861380000{len(username) % 10:04d}",
        password_hash=make_password(password),
        nickname=username,
        role=roles[role_code],
        status=status,
        auth_mode="PASSWORD",
        created_at=now,
        updated_at=now,
    )
    UserQuota.objects.create(
        user=user,
        max_instances=5,
        max_cpu_millicores=4000,
        max_memory_mb=8192,
        max_disk_mb=51200,
        max_vm_count=2,
        max_gpu_count=1,
        created_at=now,
        updated_at=now,
    )
    return user


def grant_permission(role: Role, permission_code: str, module: str = "IDENTITY") -> Permission:
    permission = Permission.objects.create(
        permission_code=permission_code,
        module=module,
        description=permission_code,
        created_at=datetime.now(UTC),
    )
    RolePermission.objects.create(role=role, permission=permission, created_at=datetime.now(UTC))
    return permission


@pytest.fixture
def active_membership(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    membership = {"membership_id": "membership-1", "status": "ACTIVE"}
    monkeypatch.setattr("apps.identity.services.auth.get_membership", lambda _user_id: membership)
    monkeypatch.setattr(
        "apps.identity.services.membership.get_membership", lambda _user_id: membership
    )
    return membership
