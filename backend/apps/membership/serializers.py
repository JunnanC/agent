from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.identity.selectors import mask_phone

from .blocking import task_stats_provider
from .constants import JOIN_SOURCE_API_VALUES, MEMBERSHIP_STATUSES
from .models import TeamMembership


def _utc(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _mask_email(value: str | None) -> str | None:
    if not value or "@" not in value:
        return value
    local, domain = value.rsplit("@", 1)
    masked_local = local[:2] + "***" if len(local) > 2 else "***"
    return f"{masked_local}@{domain}"


class MembershipApplicationSerializer(serializers.Serializer):
    team_id = serializers.IntegerField()
    message = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate_team_id(self, value: int) -> int:
        if value != 1:
            raise serializers.ValidationError("team_id must be 1")
        return value


class MembershipExitSerializer(serializers.Serializer):
    team_id = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate_team_id(self, value: int) -> int:
        if value != 1:
            raise serializers.ValidationError("team_id must be 1")
        return value


class MembershipReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("APPROVE", "REJECT"))
    review_note = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["action"] == "REJECT" and not attrs.get("review_note"):
            raise serializers.ValidationError({"review_note": "REJECT时必填"})
        return attrs


class MembershipAddSerializer(serializers.Serializer):
    team_id = serializers.IntegerField(required=False, default=1)
    username = serializers.RegexField(r"^[A-Za-z0-9_]{1,64}$")

    def validate_team_id(self, value: int) -> int:
        if value != 1:
            raise serializers.ValidationError("team_id must be 1")
        return value


class MembershipRemoveSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


def serialize_membership(membership: TeamMembership, team_name: str) -> dict[str, Any]:
    return {
        "membership_id": membership.id,
        "team_id": membership.team_id,
        "team_name": team_name,
        "membership_no": membership.membership_no,
        "status": membership.status,
        "join_source": JOIN_SOURCE_API_VALUES[membership.join_source],
        "applied_at": _utc(membership.requested_at),
        "reviewed_at": _utc(membership.reviewed_at),
        "review_note": membership.reject_reason,
        "blocking_reasons": membership.last_block_check_json or [],
    }


def serialize_application_result(
    membership: TeamMembership, team_name: str, message: str
) -> dict[str, Any]:
    return {
        "membership_id": membership.id,
        "team_name": team_name,
        "membership_no": membership.membership_no,
        "status": membership.status,
        "join_source": JOIN_SOURCE_API_VALUES[membership.join_source],
        "applied_at": _utc(membership.requested_at),
        "message": message,
    }


def serialize_exit_result(membership: TeamMembership) -> dict[str, Any]:
    return {
        "membership_id": membership.id,
        "status": membership.status,
        "exited_at": _utc(membership.exited_at),
    }


def serialize_teaching_member(
    membership: TeamMembership, user: Any, team_name: str
) -> dict[str, Any]:
    stats = task_stats_provider()
    return {
        "membership_id": membership.id,
        "user_id": membership.user_id,
        "username": user.username,
        "email": _mask_email(user.email),
        "phone": mask_phone(user.phone),
        "team_name": team_name,
        "membership_no": membership.membership_no,
        "status": membership.status,
        "join_source": JOIN_SOURCE_API_VALUES[membership.join_source],
        "applied_at": _utc(membership.requested_at),
        "reviewed_at": _utc(membership.reviewed_at),
        "blocking_count": stats.get_blocking_count(membership.user_id),
        "active_task_count": stats.get_active_task_count(membership.user_id),
    }


def validate_status_filter(value: str | None) -> set[str]:
    if not value:
        return set()
    statuses = {item.strip() for item in value.split(",") if item.strip()}
    invalid = statuses - MEMBERSHIP_STATUSES
    if invalid:
        raise serializers.ValidationError(f"invalid status: {','.join(sorted(invalid))}")
    return statuses
