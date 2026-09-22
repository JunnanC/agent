from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

import redis
from django.conf import settings
from django.http import HttpRequest, HttpResponse

from .constants import IDEMPOTENCY_KEY_HEADER
from .errors import (
    IDEMPOTENCY_CONFLICT,
    INTERNAL_ERROR,
    VALIDATION_ERROR,
    ApiError,
    error_response,
)
from .providers import actor_identifier

ViewFunc = Callable[..., HttpResponse]

_ACQUIRE_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 0 then
    redis.call('HSET', KEYS[1], 'request_digest', ARGV[1], 'state', 'PENDING')
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    return 1
end
if redis.call('HGET', KEYS[1], 'request_digest') ~= ARGV[1] then
    return -1
end
if redis.call('HGET', KEYS[1], 'state') == 'COMPLETED' then
    return 2
end
return 0
"""


def redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.CACHES["default"]["LOCATION"], decode_responses=True)


def _request_digest(request: HttpRequest, scope: str, user_id: str | None) -> str:
    params = request.query_params if hasattr(request, "query_params") else request.GET
    body = request.body if request.body else b""
    payload = {
        "method": request.method,
        "scope": scope,
        "path": request.path,
        "query": dict(params.items()),
        "body": body.decode("utf-8", errors="replace"),
        "user_id": user_id,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _idempotency_key(request: HttpRequest) -> str:
    value = request.headers.get(IDEMPOTENCY_KEY_HEADER, "")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ApiError(
            VALIDATION_ERROR,
            message="Idempotency-Key必须为UUID",
            details=[{"field": "Idempotency-Key", "issue": "必须为UUID"}],
        ) from exc
    if str(parsed) != value.lower():
        raise ApiError(
            VALIDATION_ERROR,
            message="Idempotency-Key必须为UUID",
            details=[{"field": "Idempotency-Key", "issue": "必须为UUID"}],
        )
    return value.lower()


def _record_key(scope: str, user_id: str | None, idempotency_key: str) -> str:
    return f"idempotency:{user_id or 'anonymous'}:{scope}:{idempotency_key}"


def _record_identity(request: HttpRequest, user_id: str | None) -> str | None:
    """Keep replay identity stable even when the operation revokes a token."""
    authorization = request.headers.get("Authorization", "")
    if authorization:
        return f"token:{hashlib.sha256(authorization.encode('utf-8')).hexdigest()}"
    if user_id:
        return user_id
    return None


def _response_body(response: HttpResponse) -> str:
    if hasattr(response, "render") and callable(getattr(response, "render", None)):
        response.render()
    return response.content.decode("utf-8", errors="replace")


def _replay_response(record: dict[str, str]) -> HttpResponse:
    response = HttpResponse(
        content=record.get("response_body", ""),
        status=int(record.get("http_status", 200)),
        content_type=record.get("content_type", "application/json"),
    )
    for header, value in json.loads(record.get("headers", "{}")).items():
        response[header] = value
    return response


def _wait_for_completion(client: redis.Redis, key: str, timeout: float = 30.0) -> dict[str, str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = client.hgetall(key)
        if record.get("state") == "COMPLETED":
            return record
        time.sleep(0.05)
    raise ApiError(INTERNAL_ERROR, message="幂等请求处理超时")


def idempotent(scope: str) -> Callable[[ViewFunc], ViewFunc]:
    def decorator(view_func: ViewFunc) -> ViewFunc:
        def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if request.method in {"GET", "HEAD", "OPTIONS"}:
                return view_func(request, *args, **kwargs)

            idempotency_key = _idempotency_key(request)
            user_id = actor_identifier(request)
            record_identity = _record_identity(request, user_id)
            digest = _request_digest(request, scope, record_identity)
            key = _record_key(scope, record_identity, idempotency_key)
            client = redis_client()
            result = client.eval(
                _ACQUIRE_SCRIPT,
                1,
                key,
                digest,
                settings.COMMON_IDEMPOTENCY_TTL_SECONDS,
            )

            if result == -1:
                return error_response(IDEMPOTENCY_CONFLICT)
            if result == 2:
                return _replay_response(client.hgetall(key))
            if result == 0:
                return _replay_response(_wait_for_completion(client, key))

            try:
                response = view_func(request, *args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                # Keep the exact error response for later idempotent replay.
                if isinstance(exc, ApiError):
                    response = error_response(
                        exc.error, details=exc.details, message=exc.error_message
                    )
                else:
                    response = error_response(INTERNAL_ERROR)
                _complete(client, key, digest, response)
                return response

            _complete(client, key, digest, response)
            return response

        return wrapped

    return decorator


def _complete(
    client: redis.Redis,
    key: str,
    digest: str,
    response: HttpResponse,
) -> None:
    headers = {name: response.get(name) for name in ("Content-Type", "X-Request-ID")}
    client.hset(
        key,
        mapping={
            "request_digest": digest,
            "state": "COMPLETED",
            "http_status": str(response.status_code),
            "response_body": _response_body(response),
            "content_type": response.get("Content-Type", "application/json"),
            "headers": json.dumps(headers, ensure_ascii=False),
        },
    )
    client.expire(key, settings.COMMON_IDEMPOTENCY_TTL_SECONDS)
