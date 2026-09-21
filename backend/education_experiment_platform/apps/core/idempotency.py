"""请求幂等（doc 02 §七）。

契约：``Idempotency-Key`` + actor/endpoint/request digest 组成唯一记录。

* 同键同摘要 → 直接回放首次响应，不重复执行副作用。
* 同键不同摘要 → ``IDEMPOTENCY_KEY_REUSED``（客户端复用了键但改了请求体）。
* 同键仍在处理中 → ``IDEMPOTENCY_IN_PROGRESS``，客户端应退避重试。

记录与业务写入在**同一事务**：业务回滚时幂等记录一起消失，
因此「回滚掉的请求」不会占住键，也不会被误回放成成功。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.utils import timezone

from .errors import IDEMPOTENCY_IN_PROGRESS, IDEMPOTENCY_KEY_REUSED, VALIDATION_ERROR, ApiError
from .models import IdempotencyRecord

IDEMPOTENCY_HEADER = "Idempotency-Key"
DEFAULT_TTL_SECONDS = 86400


@dataclass(frozen=True, slots=True)
class Replay:
    """命中的历史响应。"""

    status: int
    body: dict[str, Any]


def parse_idempotency_key(request: HttpRequest) -> str:
    """读取并规范化幂等键。

    要求标准 UUID：允许大小写混写但统一转小写存储，
    否则 ``AB..`` 与 ``ab..`` 会被当成两个键，重复执行副作用。
    """
    raw = (request.headers.get(IDEMPOTENCY_HEADER) or "").strip()
    if not raw:
        raise ApiError(
            VALIDATION_ERROR, detail={"header": IDEMPOTENCY_HEADER, "issue": "缺少幂等键"}
        )
    try:
        parsed = uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(
            VALIDATION_ERROR, detail={"header": IDEMPOTENCY_HEADER, "issue": "必须是 UUID"}
        ) from exc
    return str(parsed)


def request_digest(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def reserve_idempotency(
    *,
    scope: str,
    actor_ref: str,
    key: str,
    payload: Any,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> tuple[IdempotencyRecord | None, Replay | None]:
    """占位幂等键。

    返回 ``(record, None)`` 表示本次请求应继续执行，完成后必须调用
    ``store_idempotency_response``；返回 ``(None, Replay)`` 表示直接回放历史响应。
    """
    digest = request_digest(payload)
    with transaction.atomic():
        existing = (
            IdempotencyRecord.objects.select_for_update()
            .filter(actor_ref=actor_ref, endpoint=scope, key=key)
            .first()
        )
        if existing is not None:
            return _replay_or_reject(existing, digest)

        try:
            record = IdempotencyRecord.objects.create(
                key=key,
                actor_ref=actor_ref,
                endpoint=scope,
                request_digest=digest,
                response_status=0,
                response_body={},
                expires_at=timezone.now() + timezone.timedelta(seconds=ttl_seconds),
            )
        except IntegrityError:
            # 并发同键：另一个请求刚插入但尚未提交响应。让本次请求退避重试，
            # 而不是当成「键被复用」——后者会让客户端的合法重试被误判为错误。
            raise ApiError(IDEMPOTENCY_IN_PROGRESS, detail={"key": key}) from None
        return record, None


def store_idempotency_response(
    record: IdempotencyRecord, *, status: int, body: dict[str, Any]
) -> None:
    IdempotencyRecord.objects.filter(id=record.id).update(
        response_status=status, response_body=body
    )


def _replay_or_reject(existing: IdempotencyRecord, digest: str) -> tuple[None, Replay]:
    if existing.request_digest != digest:
        raise ApiError(
            IDEMPOTENCY_KEY_REUSED,
            detail={"key": existing.key, "scope": existing.endpoint},
        )
    if existing.response_status == 0:
        # 记录已存在但响应还没写完：首次请求仍在进行中。
        raise ApiError(IDEMPOTENCY_IN_PROGRESS, detail={"key": existing.key})
    return None, Replay(status=existing.response_status, body=existing.response_body)
