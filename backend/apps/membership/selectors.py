from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet

from apps.identity.selectors import visible_users

from .authorization import authorized_scope_provider
from .constants import (
    JOIN_SOURCE_APPLY,
    MEMBERSHIP_STATUS_ACTIVE,
    MEMBERSHIP_STATUS_PENDING,
    MEMBERSHIP_STATUS_REJECTED,
)
from .models import TeamMembership


def user_memberships(
    *,
    user_id: int,
    team_id: int | None = None,
    status: str | None = None,
) -> QuerySet[TeamMembership]:
    queryset = TeamMembership.objects.filter(user_id=user_id).select_related("team")
    if team_id is not None:
        queryset = queryset.filter(team_id=team_id)
    if status:
        queryset = queryset.filter(status=status)
    return queryset.order_by("-updated_at", "-id")


def teaching_members(
    actor: Any,
    *,
    statuses: set[str],
    keyword: str | None,
) -> QuerySet[TeamMembership]:
    queryset = TeamMembership.objects.select_related("team")
    if actor.role_code == "ORG_SUB_ADMIN":
        # CONFLICT-C8: 裁决前 ORG_SUB_ADMIN 只读，且默认无团队成员管理入口。
        authorized_ids = authorized_scope_provider().authorized_user_ids(actor.id)
        queryset = queryset.filter(user_id__in=authorized_ids)
    if statuses:
        queryset = queryset.filter(status__in=statuses)
    if keyword:
        user_ids = (
            visible_users()
            .filter(
                Q(username__icontains=keyword)
                | Q(email__icontains=keyword)
                | Q(phone__icontains=keyword)
            )
            .values_list("id", flat=True)
        )
        queryset = queryset.filter(user_id__in=list(user_ids))
    return queryset.order_by("-updated_at", "-id")


def teaching_applications(*, status: str) -> QuerySet[TeamMembership]:
    queryset = TeamMembership.objects.filter(join_source=JOIN_SOURCE_APPLY).select_related("team")
    if status == MEMBERSHIP_STATUS_REJECTED:
        queryset = queryset.filter(status=MEMBERSHIP_STATUS_REJECTED)
    else:
        queryset = queryset.filter(status=MEMBERSHIP_STATUS_PENDING)
    return queryset.order_by("requested_at", "id")


def membership_summary(queryset: QuerySet[TeamMembership]) -> dict[str, int]:
    return {
        "total_members": queryset.count(),
        "active_count": queryset.filter(status=MEMBERSHIP_STATUS_ACTIVE).count(),
        "pending_count": queryset.filter(status=MEMBERSHIP_STATUS_PENDING).count(),
        "blocked_count": 0,
        "pending_applications": queryset.filter(
            join_source=JOIN_SOURCE_APPLY, status=MEMBERSHIP_STATUS_PENDING
        ).count(),
    }


def users_by_membership(memberships: list[TeamMembership]) -> dict[int, Any]:
    user_ids = [membership.user_id for membership in memberships]
    users = visible_users().filter(id__in=user_ids)
    return {user.id: user for user in users}
