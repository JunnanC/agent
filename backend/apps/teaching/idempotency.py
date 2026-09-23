"""教师端幂等入口。

实现复用 apps.common.idempotency.idempotent（Redis 占位 + 结果重放 + 摘要冲突 40902）。
本模块只做一件事：把 scope 收敛到 constants.IDEMPOTENCY_SCOPES，禁止视图里写字面量，
拼错 scope 会在导入期直接失败，而不是悄悄产生一个新的幂等命名空间。
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpResponse

from apps.common.idempotency import idempotent

from .constants import IDEMPOTENCY_SCOPES

ViewFunc = Callable[..., HttpResponse]


def teaching_idempotent(scope: str) -> Callable[[ViewFunc], ViewFunc]:
    """给教师端写接口加幂等。scope 必须已在 constants.py 注册。"""

    if scope not in IDEMPOTENCY_SCOPES:
        raise ValueError(f"未注册的教师端幂等 scope: {scope}")
    return idempotent(scope)
