from __future__ import annotations

from rest_framework import serializers

from .models import User, UserQuota
from .selectors import mask_phone, mask_real_name, user_permission_codes


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=1, max_length=50)
    password = serializers.CharField(min_length=1, max_length=128)


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class UserSummarySerializer(serializers.ModelSerializer):
    role_code = serializers.CharField(source="role.role_code", read_only=True)
    role_name = serializers.CharField(source="role.role_name", read_only=True)
    membership_status = serializers.SerializerMethodField()
    membership_id = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "phone",
            "role_code",
            "role_name",
            "status",
            "membership_status",
            "membership_id",
            "permissions",
        )

    def get_membership_status(self, user: User) -> str | None:
        membership = self.context.get("membership")
        return membership.get("status") if membership else None

    def get_membership_id(self, user: User) -> str | None:
        membership = self.context.get("membership")
        return membership.get("membership_id") if membership else None

    def get_permissions(self, user: User) -> list[str]:
        return user_permission_codes(user)


class AdminUserSerializer(UserSummarySerializer):
    phone = serializers.SerializerMethodField()
    nickname = serializers.CharField(read_only=True)
    auth_mode = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta(UserSummarySerializer.Meta):
        fields = UserSummarySerializer.Meta.fields + (
            "nickname",
            "auth_mode",
            "created_at",
            "updated_at",
        )

    def get_phone(self, user: User) -> str | None:
        return mask_phone(user.phone)


class CreateUserSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=("single", "batch"))
    username = serializers.RegexField(r"^[A-Za-z0-9_]{3,64}$", required=False)
    password = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    phone = serializers.RegexField(r"^\+?[1-9]\d{6,14}$", required=False, allow_blank=True)
    role_id = serializers.IntegerField(required=False)
    import_file_key = serializers.CharField(required=False)
    send_welcome = serializers.BooleanField(default=True)

    def validate_password(self, value: str) -> str:
        if (
            len(value) < 8
            or value.islower()
            or value.isupper()
            or value.isalpha()
            or value.isdigit()
        ):
            raise serializers.ValidationError("密码最少8位且需包含大小写字母与数字")
        return value

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        mode = attrs.get("mode")
        if mode == "single":
            required = ("username", "password", "email", "role_id")
            missing = [field for field in required if not attrs.get(field)]
            if missing:
                raise serializers.ValidationError({field: "必填" for field in missing})
        elif not attrs.get("import_file_key"):
            raise serializers.ValidationError({"import_file_key": "必填"})
        return attrs


class UpdateUserSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("ACTIVE", "DISABLED"), required=False)
    role_id = serializers.IntegerField(required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError("至少提供一个字段")
        return attrs


class QuotaSerializer(serializers.ModelSerializer):
    max_concurrent_instances = serializers.IntegerField(source="max_instances")
    used_concurrent_instances = serializers.IntegerField(source="used_instances")
    max_cpu = serializers.IntegerField(source="max_cpu_millicores")
    used_cpu = serializers.IntegerField(source="used_cpu_millicores")
    max_memory = serializers.IntegerField(source="max_memory_mb")
    used_memory = serializers.IntegerField(source="used_memory_mb")
    max_storage = serializers.IntegerField(source="max_disk_mb")
    used_storage = serializers.IntegerField(source="used_disk_mb")
    max_gpu = serializers.IntegerField(source="max_gpu_count")
    used_gpu = serializers.IntegerField(source="used_gpu_count")

    class Meta:
        model = UserQuota
        fields = (
            "max_concurrent_instances",
            "used_concurrent_instances",
            "max_cpu",
            "used_cpu",
            "max_memory",
            "used_memory",
            "max_storage",
            "used_storage",
            "max_gpu",
            "used_gpu",
        )


class VerificationSerializer(serializers.Serializer):
    verification_type = serializers.CharField()
    status = serializers.CharField()
    real_name = serializers.SerializerMethodField()

    def get_real_name(self, value: dict[str, str]) -> str:
        return mask_real_name(value.get("real_name"))
