from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from django.conf import settings
from django.http import HttpRequest
from django.utils.module_loading import import_string

from .errors import INTERNAL_ERROR, ApiError


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    scope: str
    object_ids: frozenset[str] | None = None


@runtime_checkable
class PrincipalPermissionProvider(Protocol):
    def get_permission(self, actor_user_id: str, action: str) -> PermissionDecision: ...


@runtime_checkable
class AuditableActorProvider(Protocol):
    def get_actor(self, request: HttpRequest) -> tuple[str | None, str | None]: ...


def load_provider(setting_name: str) -> object | None:
    provider_path = getattr(settings, setting_name, "")
    if not provider_path:
        return None
    try:
        provider = import_string(provider_path)
        return provider() if isinstance(provider, type) else provider
    except ImportError as exc:
        raise ApiError(INTERNAL_ERROR, message="扩展提供者加载失败") from exc


def actor_identifier(request: HttpRequest) -> str | None:
    provider = load_provider("COMMON_AUDITABLE_ACTOR_PROVIDER")
    if provider is not None:
        user_id, _ = provider.get_actor(request)
        return user_id
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return str(getattr(user, "id", ""))
    return None


def actor_role(request: HttpRequest) -> str | None:
    provider = load_provider("COMMON_AUDITABLE_ACTOR_PROVIDER")
    if provider is not None:
        _, role = provider.get_actor(request)
        return role
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return str(getattr(user, "role_code", None) or getattr(user, "role", None) or "")
    return None


def principal_permission(actor_user_id: str, action: str) -> PermissionDecision:
    provider = load_provider("COMMON_PRINCIPAL_PERMISSION_PROVIDER")
    if provider is None:
        raise ApiError(INTERNAL_ERROR, message="权限提供者未配置")
    return provider.get_permission(actor_user_id, action)
