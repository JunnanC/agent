"""审计事实写入（doc 05 §六）。

两条硬规则：
1. **不落敏感值**：证件号、密码、Cookie、工作区票据、签名 URL 一律不进审计。
   调用方应先脱敏，``record_audit`` 再按敏感键名递归兜底一次，
   因为「忘记脱敏」是这类代码最常见的失误。
2. **失败也要留痕**：权限拒绝、状态冲突同样写审计（``result=FAILED``），
   否则无法解释「谁在什么时候尝试过什么」。
"""

from __future__ import annotations

import hashlib
from typing import Any

from django.conf import settings

from .models import AuditLog

RESULT_SUCCESS = "SUCCESS"
RESULT_FAILED = "FAILED"

# 键名匹配即脱敏。用小写包含匹配而不是精确匹配，是为了覆盖
# ``redis_cache_url``、``new_password`` 这类带前缀/后缀的命名。
SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
    "credential",
    "signature",
    "certificate",
    "id_card",
    "idcard",
    "phone",
    "email",
)

MASK = "***"


def mask_mapping(value: Any) -> Any:
    """递归脱敏：命中敏感键名的值替换为 ``***``，其余原样保留。"""
    if isinstance(value, dict):
        return {
            key: (MASK if _is_sensitive(key) else mask_mapping(item)) for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [mask_mapping(item) for item in value]
    return value


def hash_client_ip(ip_address: str) -> str:
    """客户端 IP 只存加盐哈希：审计需要可关联性，不需要可还原性。"""
    if not ip_address:
        return ""
    salt = getattr(settings, "AUDIT_HASH_SALT", "") or settings.SECRET_KEY
    return hashlib.sha256(f"{salt}:{ip_address}".encode()).hexdigest()


def record_audit(
    *,
    actor_ref: str,
    actor_portal: str,
    action: str,
    target_type: str,
    target_id: str,
    actor_qualification: str = "",
    course_ref: str = "",
    before: Any = None,
    after: Any = None,
    result: str = RESULT_SUCCESS,
    error_code: str = "",
    trace_id: str = "",
    client_ip: str = "",
    user_agent: str = "",
) -> AuditLog:
    return AuditLog.objects.create(
        actor_ref=actor_ref,
        actor_portal=actor_portal,
        actor_qualification=actor_qualification,
        action=action,
        course_ref=course_ref,
        target_type=target_type,
        target_id=target_id,
        before_masked=mask_mapping(before) if before is not None else None,
        after_masked=mask_mapping(after) if after is not None else None,
        result=result,
        error_code=error_code,
        client_ip_hash=hash_client_ip(client_ip),
        user_agent_summary=user_agent[:128],
        trace_id=trace_id,
    )


def _is_sensitive(key: Any) -> bool:
    name = str(key).lower()
    return any(part in name for part in SENSITIVE_KEY_PARTS)
