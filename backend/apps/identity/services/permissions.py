from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from apps.common.errors import FORBIDDEN, ApiError
from apps.common.providers import PermissionDecision

from ..selectors import user_permission_codes, user_verification
from .auth import authenticate_request
from .membership import get_membership, membership_service

ROLE_SCOPES = {
    "USER": "SELF",
    "ORG_SUB_ADMIN": "AUTHORIZED",
    "ORG_ADMIN": "ALL",
    "SYSTEM_ADMIN": "ALL",
}


def resolve_scope(user: Any, action: str) -> str:
    role_code = getattr(user, "role_code", None) or user.get("role_code", "")
    scope = ROLE_SCOPES.get(role_code, "NONE")
    if action.startswith("runtime:") and _unverified_denied(user):
        return "NONE"
    return scope


def can(user: Any, action: str, resource_scope: Any = None) -> bool:
    scope = resolve_scope(user, action)
    if scope == "NONE":
        return False
    if action not in user_permission_codes(user):
        return False
    if scope == "SELF":
        return getattr(resource_scope, "owner_user_id", None) == user.id
    if scope == "AUTHORIZED":
        return user.id in getattr(resource_scope, "authorized_user_ids", [])
    return True


class IdentityPrincipalPermissionProvider:
    def get_permission(self, actor_user_id: str, action: str) -> PermissionDecision:
        from ..selectors import get_user

        user = get_user(actor_user_id)
        if user is None or user.status != "ACTIVE":
            return PermissionDecision(allowed=False, scope="NONE")
        scope = resolve_scope(user, action)
        allowed = scope != "NONE" and action in user_permission_codes(user)
        return PermissionDecision(allowed=allowed, scope=scope)


class IsAuthenticated:
    def has_permission(self, request: HttpRequest, view: Any) -> bool:
        try:
            authenticate_request(request)
            return True
        except ApiError:
            return False


class IsSystemAdmin:
    def has_permission(self, request: HttpRequest, view: Any) -> bool:
        try:
            user, _ = authenticate_request(request)
            return user.role_code == "SYSTEM_ADMIN"
        except ApiError:
            return False


class HasActionPermission:
    def __init__(self, action: str) -> None:
        self.action = action

    def has_permission(self, request: HttpRequest, view: Any) -> bool:
        try:
            user, _ = authenticate_request(request)
        except ApiError:
            return False
        provider = IdentityPrincipalPermissionProvider()
        return provider.get_permission(str(user.id), self.action).allowed


def require_authenticated(request: HttpRequest) -> Any:
    user, _ = authenticate_request(request)
    request.identity_user_id = str(user.id)
    request.identity_role_code = user.role_code
    return user


def require_system_admin(request: HttpRequest) -> Any:
    user, _ = authenticate_request(request)
    request.identity_user_id = str(user.id)
    request.identity_role_code = user.role_code
    if user.role_code != "SYSTEM_ADMIN":
        raise ApiError(FORBIDDEN)
    return user


def require_action(request: HttpRequest, action: str, resource_scope: Any = None) -> None:
    user, _ = authenticate_request(request)
    if not can(user, action, resource_scope):
        raise ApiError(FORBIDDEN)


def get_role(user_id: int | str) -> str:
    from ..selectors import get_user

    user = get_user(user_id)
    return user.role_code if user else ""


def _unverified_denied(user: Any) -> bool:
    verification = user_verification(user.id)
    approved = verification is not None and verification.status == "APPROVED"
    if approved:
        return False
    membership = get_membership(user.id)
    if not membership:
        return True
    return membership_service().unverified_start_policy(membership["membership_id"]) == "DENIED"
