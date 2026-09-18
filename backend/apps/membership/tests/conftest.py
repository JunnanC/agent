from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from django.db import connection

from apps.common.models import AuditLog, OutboxEvent
from apps.identity.models import Permission, Role, RolePermission, User
from apps.membership.models import TeamMembership, TeamSettings


def _drop_tables() -> None:
    tables = (
        "team_memberships",
        "team_settings",
        "role_permissions",
        "permissions",
        "users",
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
            AuditLog,
            OutboxEvent,
            TeamSettings,
            TeamMembership,
        ):
            editor.create_model(model)


@pytest.fixture
def membership_tables(transactional_db: None) -> Iterator[None]:
    _drop_tables()
    _create_tables()
    try:
        yield
    finally:
        _drop_tables()


@pytest.fixture
def team_settings(membership_tables: None) -> TeamSettings:
    now = datetime.now(UTC)
    return TeamSettings.objects.create(
        id=1,
        team_name="实验团队",
        team_code="TEAM001",
        auth_password_enabled=True,
        auth_school_enabled=False,
        auth_enterprise_enabled=False,
        unverified_start_policy="DENIED",
        default_report_required=True,
        default_review_mode="MANUAL",
        default_archive_retention_days=365,
        default_audit_retention_days=365,
        default_runtime_log_retention_days=90,
        updated_by_id=None,
        max_attachment_size_mb=100,
        allowed_attachment_mime=["application/pdf"],
        storage_alert_warn_percent=80,
        storage_alert_critical_percent=90,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def roles(membership_tables: None) -> dict[str, Role]:
    now = datetime.now(UTC)
    return {
        role_code: Role.objects.create(
            role_code=role_code,
            role_name=role_code,
            is_system=True,
            created_at=now,
            updated_at=now,
        )
        for role_code in ("SYSTEM_ADMIN", "ORG_ADMIN", "ORG_SUB_ADMIN", "USER")
    }


def make_user(
    roles: dict[str, Role],
    *,
    username: str,
    role_code: str = "USER",
) -> User:
    now = datetime.now(UTC)
    return User.objects.create(
        username=username,
        email=f"{username}@example.com",
        phone=f"+8613800{len(username):07d}",
        password_hash="",
        nickname=username,
        role=roles[role_code],
        status="ACTIVE",
        auth_mode="PASSWORD",
        created_at=now,
        updated_at=now,
    )


def make_membership(
    *,
    user_id: int,
    status: str,
    join_source: str = "APPLY",
    created_by_id: int | None = None,
) -> TeamMembership:
    now = datetime.now(UTC)
    return TeamMembership.objects.create(
        team_id=1,
        membership_no=f"TM2026{user_id:08d}",
        user_id=user_id,
        status=status,
        join_source=join_source,
        previous_status="",
        requested_at=now,
        created_by_id=created_by_id,
        created_at=now,
        updated_at=now,
    )
