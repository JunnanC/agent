from __future__ import annotations

from typing import Literal

from django.http import HttpRequest

from .errors import FORBIDDEN, ApiError
from .providers import actor_role

RouteScope = Literal["me", "teaching", "admin"]
PermissionScope = Literal["SELF", "AUTHORIZED", "ALL", "NONE"]

ROLE_MATRIX: dict[str, dict[RouteScope, PermissionScope]] = {
    "USER": {"me": "SELF", "teaching": "NONE", "admin": "NONE"},
    "ORG_SUB_ADMIN": {"me": "SELF", "teaching": "AUTHORIZED", "admin": "NONE"},
    "ORG_ADMIN": {"me": "SELF", "teaching": "ALL", "admin": "NONE"},
    "SYSTEM_ADMIN": {"me": "SELF", "teaching": "NONE", "admin": "ALL"},
}


def route_permission(role: str | None, route: RouteScope) -> PermissionScope:
    return ROLE_MATRIX.get(role or "", {}).get(route, "NONE")


def require_route_permission(request: HttpRequest, route: RouteScope) -> PermissionScope:
    permission = route_permission(actor_role(request), route)
    if permission == "NONE":
        raise ApiError(FORBIDDEN)
    return permission


def require_system_admin(request: HttpRequest) -> None:
    if actor_role(request) != "SYSTEM_ADMIN":
        raise ApiError(FORBIDDEN)
