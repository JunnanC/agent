from __future__ import annotations

from celery import shared_task

from .audit_export import run_audit_export
from .outbox import dispatch_due_outbox

# run_audit_export 定义在 audit_export.py，不在 autodiscover 扫描的 tasks.py 内。
# 它目前仅因 Celery 启动时执行 Django 系统检查（含 URL 检查）顺带导入 config.urls 而注册。
# 一旦设置 CELERY_SKIP_CHECKS=1，该任务会从注册表静默消失；此显式导入用于消除该依赖。
__all__ = ["dispatch_outbox", "run_audit_export"]


@shared_task(name="apps.common.dispatch_outbox")
def dispatch_outbox() -> int:
    return dispatch_due_outbox()
