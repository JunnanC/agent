from __future__ import annotations

from django.db.models import QuerySet

from .models import Permission, Role, RolePermission, User, UserVerification


def mask_phone(value: str | None) -> str | None:
    if not value:
        return value
    if len(value) <= 8:
        return "*" * len(value)
    return value[:3] + "****" + value[-4:]


def mask_real_name(value: str | None) -> str | None:
    if not value:
        return value
    return value[0] + "*" * max(len(value) - 1, 1)


def visible_users() -> QuerySet[User]:
    return User.objects.filter(deleted_at__isnull=True).select_related("role")


def get_user(user_id: int | str) -> User | None:
    return visible_users().filter(id=user_id).first()


def get_builtin_role(role_id: int | str) -> Role | None:
    return Role.objects.filter(
        id=role_id, role_code__in={"SYSTEM_ADMIN", "ORG_ADMIN", "ORG_SUB_ADMIN", "USER"}
    ).first()


def user_permission_codes(user: User) -> list[str]:
    return list(
        RolePermission.objects.filter(role_id=user.role_id)
        .values_list("permission__permission_code", flat=True)
        .order_by("permission__permission_code")
    )


def user_verification(user_id: int | str) -> UserVerification | None:
    return UserVerification.objects.filter(user_id=user_id).first()


def admin_users(
    *, keyword: str | None = None, role: str | None = None, status: str | None = None
) -> QuerySet[User]:
    queryset = visible_users()
    if keyword:
        from django.db.models import Q

        queryset = queryset.filter(
            Q(username__icontains=keyword)
            | Q(email__icontains=keyword)
            | Q(phone__icontains=keyword)
        )
    if role:
        queryset = queryset.filter(role__role_code=role)
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def permission_matrix(
    *, role_code: str | None = None, resource: str | None = None
) -> list[dict[str, object]]:
    roles = Role.objects.order_by("id")
    if role_code:
        roles = roles.filter(role_code=role_code)
    permissions = Permission.objects.order_by("module", "permission_code")
    if resource:
        permissions = permissions.filter(module=resource.upper())
    permission_by_id = {permission.id: permission for permission in permissions}
    mappings = RolePermission.objects.filter(
        role_id__in=list(roles.values_list("id", flat=True)),
        permission_id__in=permission_by_id,
    ).select_related("role", "permission")
    grouped: dict[int, list[dict[str, object]]] = {role.id: [] for role in roles}
    for mapping in mappings:
        permission = permission_by_id[mapping.permission_id]
        grouped[mapping.role_id].append(
            {
                "id": permission.id,
                "perm_code": permission.permission_code,
                "resource": permission.module,
                "action": permission.permission_code.split(":", 1)[-1],
                "path": "",
                "method": "",
            }
        )
    return [
        {
            "role_id": role.id,
            "role_code": role.role_code,
            "role_name": role.role_name,
            "permissions": grouped[role.id],
        }
        for role in roles
    ]
