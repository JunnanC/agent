"""外部依赖端口（doc 02 §一：``ports.py`` 外部依赖 Protocol）。

课程域需要两件它自己不拥有的能力：

1. 请求的 actor（账号 opaque ID、门户、资格快照）——归 accounts 所有。
2. 教师资格判定——归 accounts 所有。

两者都通过 ``settings`` 注入实现。**未配置时一律拒绝**（fail-closed）：
默认放行会让「忘记配置 provider」在生产上静默变成越权入口。
V01（accounts）落地后注入真实实现即可，本模块不需要改动。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from django.conf import settings
from django.http import HttpRequest
from django.utils.module_loading import import_string

from apps.core.errors import AUTH_REQUIRED, TEACHER_QUALIFICATION_REQUIRED, ApiError

PORTAL_TEACHING = "TEACHING"

ACTOR_PROVIDER_SETTING = "COURSES_ACTOR_PROVIDER"
QUALIFICATION_PROVIDER_SETTING = "COURSES_TEACHER_QUALIFICATION_PROVIDER"


@dataclass(frozen=True, slots=True)
class Actor:
    """请求主体。``qualification`` 是快照，用于审计留痕。"""

    ref: str
    portal: str
    qualification: str = ""
    is_platform_admin: bool = False


class ActorPort(Protocol):
    def resolve(self, request: HttpRequest) -> Actor | None: ...


class TeacherQualificationPort(Protocol):
    def is_qualified(self, actor_ref: str) -> bool: ...


class DenyAllActorPort:
    """默认实现：没有任何会话来源，永远返回未认证。"""

    def resolve(self, request: HttpRequest) -> Actor | None:
        return None


class DenyAllQualificationPort:
    """默认实现：不承认任何教师资格。"""

    def is_qualified(self, actor_ref: str) -> bool:
        return False


@lru_cache(maxsize=8)
def _load(path: str) -> Any:
    return import_string(path)


def _build(setting_name: str, default_class: type[Any]) -> Any:
    path = getattr(settings, setting_name, "")
    if not path:
        return default_class()
    return _load(path)()


def get_actor(request: HttpRequest) -> Actor:
    actor = _build(ACTOR_PROVIDER_SETTING, DenyAllActorPort).resolve(request)
    if actor is None:
        raise ApiError(AUTH_REQUIRED)
    return actor


def require_teaching_portal(actor: Actor) -> None:
    """doc 02 §2.3：门户准入是第一层，先于任何对象权限判断。"""
    from apps.core.errors import PORTAL_ACCESS_DENIED

    if actor.portal != PORTAL_TEACHING:
        raise ApiError(PORTAL_ACCESS_DENIED, detail={"portal": actor.portal})


def is_teacher_qualified(actor_ref: str) -> bool:
    """平台级教师资格判定。

    单独拆出来是为了让 services 在细分场景复用（如任命助教前校验
    被任命者是否具备教师资格），而不得不去造一个假的 Actor。
    """
    port: TeacherQualificationPort = _build(
        QUALIFICATION_PROVIDER_SETTING, DenyAllQualificationPort
    )
    return port.is_qualified(actor_ref)


def require_teaching_qualification(actor: Actor) -> None:
    """doc 02 §三：创建课程需要有效教师资格，不只是能进教师端。"""
    if not is_teacher_qualified(actor.ref):
        raise ApiError(TEACHER_QUALIFICATION_REQUIRED)
