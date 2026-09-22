"""教师端准入：门户边界 + 角色矩阵。

门户只是额外边界，不替代账号授权（见 apps.common.portal.permissions.PortalPermission
的说明）。写服务在事务开始前会再校验一次，因此即使视图层漏挂权限类也不会静默放行。
"""

from __future__ import annotations

from django.http import HttpRequest

from apps.common.errors import FORBIDDEN, UNAUTHENTICATED, ApiError
from apps.common.permissions import require_route_permission
from apps.common.portal.permissions import PortalPermission
from apps.common.providers import actor_identifier

from .constants import TEACHING_PORTALS


class TeachingPortalPermission(PortalPermission):
    """DRF 权限类：只允许教学端门户访问。"""

    required_portals = TEACHING_PORTALS


def require_teaching_portal(request: HttpRequest) -> str:
    portal = getattr(request, "portal", None)
    if portal not in TEACHING_PORTALS:
        raise ApiError(FORBIDDEN, message="当前入口无权访问教师端资源")
    return portal


def require_teaching_actor(request: HttpRequest) -> str:
    """校验门户与角色矩阵，返回 actor 用户标识。

    角色矩阵取自 apps.common.permissions.ROLE_MATRIX：ORG_ADMIN 为 ALL，
    ORG_SUB_ADMIN 为 AUTHORIZED，USER 与 SYSTEM_ADMIN 为 NONE。
    """

    require_teaching_portal(request)
    require_route_permission(request, "teaching")
    actor = actor_identifier(request)
    if not actor:
        raise ApiError(UNAUTHENTICATED, message="教师端写操作需要已认证的账号")
    return actor
