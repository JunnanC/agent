"""教师端写侧服务：审计、Outbox 与事务编排。

对外只暴露三个入口，M2/M5 等切片统一复用，不要各自再写一套：
audit_teaching、publish_teaching_event、teaching_write。
"""

from __future__ import annotations

from .audit import audit_teaching
from .outbox import publish_teaching_event
from .writes import TeachingWrite, teaching_write

__all__ = [
    "TeachingWrite",
    "audit_teaching",
    "publish_teaching_event",
    "teaching_write",
]
