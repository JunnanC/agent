from __future__ import annotations

from typing import ClassVar

from django.db import models


class Role(models.Model):
    id = models.BigAutoField(primary_key=True)
    role_code = models.CharField(max_length=32, unique=True)
    role_name = models.CharField(max_length=64)
    description = models.CharField(max_length=255, blank=True, default="")
    is_system = models.BooleanField(default=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "roles"


class Permission(models.Model):
    id = models.BigAutoField(primary_key=True)
    permission_code = models.CharField(max_length=64, unique=True)
    module = models.CharField(max_length=32)
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "permissions"


class RolePermission(models.Model):
    role = models.OneToOneField(
        Role, primary_key=True, on_delete=models.DO_NOTHING, db_column="role_id"
    )
    permission = models.ForeignKey(
        Permission, on_delete=models.DO_NOTHING, db_column="permission_id"
    )
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "role_permissions"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["role", "permission"], name="pk_role_permissions")
        ]


class User(models.Model):
    class AuthMode(models.TextChoices):
        PASSWORD = "PASSWORD"
        LDAP = "LDAP"
        OIDC = "OIDC"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        DISABLED = "DISABLED"
        LOCKED = "LOCKED"

    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=64, unique=True)
    phone = models.CharField(max_length=32, unique=True, null=True)
    email = models.CharField(max_length=255, unique=True, null=True)
    password_hash = models.CharField(max_length=255, null=True)
    nickname = models.CharField(max_length=64, blank=True, default="")
    avatar_file_id = models.BigIntegerField(null=True)
    role = models.ForeignKey(Role, on_delete=models.DO_NOTHING, db_column="role_id")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    deleted_at = models.DateTimeField(null=True)
    auth_mode = models.CharField(max_length=16, choices=AuthMode.choices, default=AuthMode.PASSWORD)
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until_at = models.DateTimeField(null=True)
    last_login_at = models.DateTimeField(null=True)
    last_login_ip = models.CharField(max_length=64, blank=True, default="")
    created_by_id = models.BigIntegerField(null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "users"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["role", "status"], name="idx_users_role_status"),
            models.Index(fields=["status"], name="idx_users_status"),
        ]

    @property
    def role_code(self) -> str:
        return self.role.role_code


class UserVerification(models.Model):
    class VerificationType(models.TextChoices):
        NONE = "NONE"
        SCHOOL = "SCHOOL"
        ENTERPRISE = "ENTERPRISE"

    class Status(models.TextChoices):
        PENDING = "PENDING"
        APPROVED = "APPROVED"
        REJECTED = "REJECTED"

    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, unique=True, on_delete=models.DO_NOTHING, db_column="user_id")
    verification_type = models.CharField(max_length=32, choices=VerificationType.choices)
    status = models.CharField(max_length=16, choices=Status.choices)
    real_name = models.CharField(max_length=64)
    institution_name = models.CharField(max_length=128, blank=True, default="")
    evidence_file_id = models.BigIntegerField(null=True)
    submitted_at = models.DateTimeField(null=True)
    reviewed_at = models.DateTimeField(null=True)
    reviewed_by_id = models.BigIntegerField(null=True)
    reject_reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "user_verifications"


class UserQuota(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, unique=True, on_delete=models.DO_NOTHING, db_column="user_id")
    max_instances = models.PositiveIntegerField()
    used_instances = models.PositiveIntegerField(default=0)
    max_cpu_millicores = models.PositiveIntegerField()
    used_cpu_millicores = models.PositiveIntegerField(default=0)
    max_memory_mb = models.PositiveIntegerField()
    used_memory_mb = models.PositiveIntegerField(default=0)
    max_disk_mb = models.PositiveIntegerField()
    used_disk_mb = models.PositiveIntegerField(default=0)
    max_vm_count = models.PositiveIntegerField()
    used_vm_count = models.PositiveIntegerField(default=0)
    max_gpu_count = models.PositiveIntegerField()
    used_gpu_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "user_quotas"
