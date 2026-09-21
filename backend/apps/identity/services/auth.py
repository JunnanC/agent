from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.http import HttpRequest

from apps.common.errors import (
    ACCOUNT_DISABLED,
    MEMBERSHIP_REQUIRED,
    UNAUTHENTICATED,
    ApiError,
)

from ..selectors import get_user
from .membership import get_membership, membership_service

ACCESS_TOKEN_TTL_SECONDS = 2 * 60 * 60
REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _sign(value: bytes) -> str:
    return _b64encode(hmac.new(settings.SECRET_KEY.encode(), value, hashlib.sha256).digest())


@dataclass(frozen=True)
class IdentityClaims:
    user_id: int
    role_code: str
    membership_status: str | None
    jti: str
    exp: int


def issue_access_token(
    user_id: int, role_code: str, membership_status: str | None
) -> tuple[str, str]:
    jti = uuid.uuid4().hex
    exp = int(time.time()) + ACCESS_TOKEN_TTL_SECONDS
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(
        json.dumps(
            {
                "user_id": user_id,
                "role_code": role_code,
                "membership_status": membership_status,
                "jti": jti,
                "exp": exp,
            },
            separators=(",", ":"),
        ).encode()
    )
    token = f"{header}.{payload}.{_sign(f'{header}.{payload}'.encode())}"
    cache.set(_access_key(jti), "ACTIVE", ACCESS_TOKEN_TTL_SECONDS)
    _remember_session(user_id, jti)
    return token, jti


def issue_refresh_token(user_id: int, access_jti: str) -> str:
    token = f"{user_id}.{uuid.uuid4().hex}.{uuid.uuid4().hex}"
    record = {"user_id": user_id, "status": "ACTIVE"}
    cache.set(_refresh_key(token), record, REFRESH_TOKEN_TTL_SECONDS)
    cache.set(_access_refresh_key(access_jti), _hash_token(token), REFRESH_TOKEN_TTL_SECONDS)
    return token


def decode_access_token(token: str) -> IdentityClaims:
    try:
        header, payload, signature = token.split(".")
        expected = _sign(f"{header}.{payload}".encode())
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        claims = json.loads(_b64decode(payload))
        if claims.get("exp", 0) < time.time():
            raise ValueError
        return IdentityClaims(
            user_id=int(claims["user_id"]),
            role_code=str(claims["role_code"]),
            membership_status=claims.get("membership_status"),
            jti=str(claims["jti"]),
            exp=int(claims["exp"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ApiError(UNAUTHENTICATED) from exc


def authenticate_request(request: HttpRequest) -> tuple[Any, IdentityClaims]:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise ApiError(UNAUTHENTICATED)
    claims = decode_access_token(authorization[7:])
    if cache.get(_access_key(claims.jti)) != "ACTIVE":
        raise ApiError(UNAUTHENTICATED)
    user = get_user(claims.user_id)
    if user is None or user.status != "ACTIVE":
        raise ApiError(UNAUTHENTICATED)
    return user, claims


def login(username: str, password: str) -> dict[str, Any]:
    from apps.identity.models import User

    user = (
        User.objects.filter(username=username, deleted_at__isnull=True)
        .select_related("role")
        .first()
    )
    if user is None or not user.password_hash or not check_password(password, user.password_hash):
        raise ApiError(UNAUTHENTICATED)
    if user.status == "DISABLED":
        raise ApiError(ACCOUNT_DISABLED)
    if user.status != "ACTIVE":
        raise ApiError(UNAUTHENTICATED)
    membership = get_membership(user.id)
    if membership is None:
        raise ApiError(MEMBERSHIP_REQUIRED)
    token, jti = issue_access_token(user.id, user.role_code, membership["status"])
    refresh = issue_refresh_token(user.id, jti)
    return {
        "access_token": token,
        "refresh_token": refresh,
        "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        "token_type": "Bearer",
        "user": user,
    }


def refresh(refresh_token: str) -> dict[str, Any]:
    key = _refresh_key(refresh_token)
    record = cache.get(key)
    if not isinstance(record, dict):
        raise ApiError(UNAUTHENTICATED)
    if record.get("status") == "ROTATED":
        revoke_all_sessions(int(record["user_id"]))
        raise ApiError(UNAUTHENTICATED)
    user = get_user(record["user_id"])
    if user is None or user.status != "ACTIVE":
        raise ApiError(UNAUTHENTICATED)
    membership = get_membership(user.id)
    access, jti = issue_access_token(
        user.id, user.role_code, membership["status"] if membership else None
    )
    cache.set(key, {**record, "status": "ROTATED"}, REFRESH_TOKEN_TTL_SECONDS)
    new_refresh = issue_refresh_token(user.id, jti)
    return {
        "access_token": access,
        "refresh_token": new_refresh,
        "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        "token_type": "Bearer",
    }


def logout(request: HttpRequest) -> None:
    _, claims = authenticate_request(request)
    cache.set(_access_key(claims.jti), "REVOKED", ACCESS_TOKEN_TTL_SECONDS)
    refresh_hash = cache.get(_access_refresh_key(claims.jti))
    if refresh_hash:
        record = cache.get(f"identity:refresh:{refresh_hash}")
        if isinstance(record, dict):
            cache.set(
                f"identity:refresh:{refresh_hash}",
                {**record, "status": "REVOKED"},
                REFRESH_TOKEN_TTL_SECONDS,
            )


def revoke_all_sessions(user_id: int | str) -> None:
    user_id = int(user_id)
    jti_values = cache.get(_sessions_key(user_id), [])
    for jti in jti_values if isinstance(jti_values, list) else []:
        cache.set(_access_key(jti), "REVOKED", ACCESS_TOKEN_TTL_SECONDS)
    cache.delete(_sessions_key(user_id))
    membership_service().revoke_authentication_sessions(user_id)


def current_identity(request: HttpRequest) -> dict[str, Any]:
    user, claims = authenticate_request(request)
    membership = get_membership(user.id)
    return {
        "user": user,
        "membership": membership,
        "claims": claims,
    }


def _access_key(jti: str) -> str:
    return f"identity:access:{jti}"


def _access_refresh_key(jti: str) -> str:
    return f"identity:access-refresh:{jti}"


def _refresh_key(token: str) -> str:
    return f"identity:refresh:{_hash_token(token)}"


def _sessions_key(user_id: int) -> str:
    return f"identity:sessions:{user_id}"


def _remember_session(user_id: int, jti: str) -> None:
    values = cache.get(_sessions_key(user_id), [])
    if not isinstance(values, list):
        values = []
    if jti not in values:
        values.append(jti)
    cache.set(_sessions_key(user_id), values, REFRESH_TOKEN_TTL_SECONDS)


class IdentityAuditableActorProvider:
    def get_actor(self, request: HttpRequest) -> tuple[str | None, str | None]:
        try:
            user, _ = authenticate_request(request)
            return str(user.id), user.role_code
        except ApiError:
            return None, None
