"""教师端写事务编排。

一次教师端写操作由一个显式上下文包住，保证 Guideline 04 §4「必须落实的事务」：

    业务事实 + 审计 + Outbox 在同一事务内提交

退出路径（对齐 D5）：

* 正常退出：写 SUCCESS 审计，再派发本次登记的事件，然后提交。
* write.deny(error)：业务事实本就不成立，事务内只写 DENIED 审计，
  事务提交后再抛出 error，保证拒绝留痕不会被回滚。
* 调用方抛异常：整事务回滚，业务事实、审计、Outbox 一起回滚。

不使用信号、不重写 Model.save、不做基类自动埋点：事务内的写入顺序与回滚语义
必须一眼可读（Guideline 03 §5）。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from django.http import HttpRequest

from apps.common.errors import INTERNAL_ERROR, ApiError

from ..constants import AUDIT_RESULT_DENIED, AUDIT_RESULT_SUCCESS
from ..permissions import require_teaching_actor
from .audit import audit_teaching
from .outbox import publish_teaching_event


@dataclass(frozen=True)
class _PendingEvent:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    topic: str
    payload: dict[str, Any] | None = None


@dataclass
class TeachingWrite:
    """一次教师端写事务的可变状态，由 teaching_write() 注入调用方。"""

    action: str
    target_type: str
    target_id: str
    assignment_id: str | None = None
    instance_id: str | None = None
    before: Any = None
    after: Any = None
    _events: list[_PendingEvent] = field(default_factory=list, repr=False)
    _denied: ApiError | None = field(default=None, repr=False)
    _deny_reason: str = field(default="", repr=False)

    def publish(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        topic: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """登记事件，退出事务前统一发布（保证顺序为审计在前、事件在后）。"""

        if self._denied is not None:
            raise ApiError(INTERNAL_ERROR, message="已标记拒绝的事务不得再登记事件")
        self._events.append(
            _PendingEvent(
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                topic=topic,
                payload=payload,
            )
        )

    def deny(self, error: ApiError, *, reason: str = "") -> None:
        """标记本事务为拒绝：不写业务事实，只留 DENIED 审计，提交后抛出 error。"""

        if self._denied is not None:
            raise ApiError(INTERNAL_ERROR, message="同一事务只能拒绝一次")
        self._denied = error
        self._deny_reason = reason


@contextmanager
def teaching_write(
    request: HttpRequest,
    *,
    action: str,
    target_type: str,
    target_id: str,
    assignment_id: str | None = None,
    instance_id: str | None = None,
) -> Iterator[TeachingWrite]:
    """教师端写事务上下文。

    进入前先做一次准入校验（门户 + 角色矩阵，写服务侧再次校验），
    未通过时不会开启事务、不会有任何副作用。
    """

    require_teaching_actor(request)
    write = TeachingWrite(
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        assignment_id=assignment_id,
        instance_id=instance_id,
    )

    with transaction.atomic():
        yield write

        if write._denied is not None:
            audit_teaching(
                request,
                action=write.action,
                target_type=write.target_type,
                target_id=write.target_id,
                result=AUDIT_RESULT_DENIED,
                reason=write._deny_reason,
                before=write.before,
                after=write.after,
                assignment_id=write.assignment_id,
                instance_id=write.instance_id,
            )
        else:
            audit_teaching(
                request,
                action=write.action,
                target_type=write.target_type,
                target_id=write.target_id,
                result=AUDIT_RESULT_SUCCESS,
                before=write.before,
                after=write.after,
                assignment_id=write.assignment_id,
                instance_id=write.instance_id,
            )
            for event in write._events:
                publish_teaching_event(
                    event_type=event.event_type,
                    aggregate_type=event.aggregate_type,
                    aggregate_id=event.aggregate_id,
                    topic=event.topic,
                    payload=event.payload,
                    assignment_id=write.assignment_id,
                    instance_id=write.instance_id,
                )

    if write._denied is not None:
        raise write._denied
