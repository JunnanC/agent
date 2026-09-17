from __future__ import annotations

from datetime import datetime

from rest_framework import serializers


class AuditFilterSerializer(serializers.Serializer):
    user_id = serializers.CharField(required=False, allow_blank=True)
    action = serializers.CharField(required=False, allow_blank=True)
    resource_type = serializers.CharField(required=False, allow_blank=True)
    resource_id = serializers.CharField(required=False, allow_blank=True)
    request_id = serializers.CharField(required=False, allow_blank=True)
    trace_id = serializers.CharField(required=False, allow_blank=True)
    assignment_id = serializers.CharField(required=False, allow_blank=True)
    instance_id = serializers.CharField(required=False, allow_blank=True)
    ip_address = serializers.CharField(required=False, allow_blank=True)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        created_after = attrs.get("created_after")
        created_before = attrs.get("created_before")
        if (
            isinstance(created_after, datetime)
            and isinstance(created_before, datetime)
            and created_after > created_before
        ):
            raise serializers.ValidationError("created_after不能晚于created_before")
        return attrs


class AuditExportSerializer(serializers.Serializer):
    filters = AuditFilterSerializer(required=True)
    format = serializers.ChoiceField(choices=("csv", "json"), default="csv")
    mask_fields = serializers.ListField(
        child=serializers.CharField(), default=["ip_address", "user_agent"]
    )


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)
