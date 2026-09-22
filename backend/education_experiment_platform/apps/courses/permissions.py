"""接口级粗粒度准入（doc 02 §一：``permissions.py`` 接口级粗粒度准入）。

这里只做「门户 + 资格」这一层，**不做对象权限**：对象级判断需要 course 实例，
必须落在 selector/service 里（doc 02 §2.3「门户准入不等于对象权限」）。
视图挂这个权限类，是为了让「错门户调用」在进入业务逻辑前就被拒绝。
"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from rest_framework.permissions import BasePermission

from apps.core.errors import PORTAL_ACCESS_DENIED, ApiError

from .ports import PORTAL_TEACHING, get_actor, require_teaching_qualification


class TeachingPortalRequired(BasePermission):
    """只接受教师门户。

    抛 ``ApiError`` 而不是返回 False：返回 False 会被 DRF 转成通用 403，
    丢失 ``PORTAL_ACCESS_DENIED`` 这个稳定 code，客户端无法区分
    「错门户」与「有权但被拒」。
    """

    def has_permission(self, request: HttpRequest, view: Any) -> bool:
        portal = getattr(request, "portal", None)
        if portal != PORTAL_TEACHING:
            raise ApiError(PORTAL_ACCESS_DENIED, detail={"portal": portal or ""})
        return True


class TeachingQualificationRequired(BasePermission):
    """教师端的第二层准入：全局教师资格（doc 02 §4.1）。

    doc 02 §三 把授权拆成 portal → 全局资格 → 课程任职 → 资源关系 → 状态/窗口，
    这里只落第二层。资格被撤销后旧会话必须立即失效
    （doc 06 §6.2），所以资格不能缓存成长生命周期事实。
    """

    def has_permission(self, request: HttpRequest, view: Any) -> bool:
        require_teaching_qualification(get_actor(request))
        return True
