from __future__ import annotations

import json
import threading
import time
import uuid

import pytest
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.test import RequestFactory

from apps.common.errors import IDEMPOTENCY_CONFLICT, ApiError
from apps.common.idempotency import idempotent


class FakeRedis:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, str]] = {}
        self.ttls: dict[str, int] = {}
        self.lock = threading.Lock()

    def eval(self, script: str, numkeys: int, key: str, digest: str, ttl: int) -> int:
        with self.lock:
            record = self.records.get(key)
            if record is None:
                self.records[key] = {"request_digest": digest, "state": "PENDING"}
                self.ttls[key] = ttl
                return 1
            if record["request_digest"] != digest:
                return -1
            return 2 if record["state"] == "COMPLETED" else 0

    def hgetall(self, key: str) -> dict[str, str]:
        with self.lock:
            return dict(self.records.get(key, {}))

    def hset(self, key: str, mapping: dict[str, str]) -> None:
        with self.lock:
            self.records.setdefault(key, {}).update(mapping)

    def expire(self, key: str, ttl: int) -> None:
        with self.lock:
            self.ttls[key] = ttl


def _request(body: bytes, key: str | None = None) -> HttpRequest:
    headers = {"HTTP_IDEMPOTENCY_KEY": key} if key else {}
    return RequestFactory().post("/test", data=body, content_type="application/json", **headers)


def test_idempotent_request_replays_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: client)
    calls = 0

    @idempotent("test")
    def view(request: HttpRequest) -> HttpResponse:
        nonlocal calls
        calls += 1
        return JsonResponse({"value": calls})

    key = str(uuid.uuid4())
    first = view(_request(b'{"value":1}', key))
    second = view(_request(b'{"value":1}', key))

    assert calls == 1
    assert first.status_code == second.status_code
    assert first.content == second.content
    assert client.ttls[f"idempotency:anonymous:test:{key}"] >= 24 * 60 * 60
    record = client.records[f"idempotency:anonymous:test:{key}"]
    assert record["state"] == "COMPLETED"
    assert record["http_status"] == "200"
    assert record["response_body"]


def test_idempotent_request_rejects_different_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: client)
    calls = 0

    @idempotent("test")
    def view(request: HttpRequest) -> HttpResponse:
        nonlocal calls
        calls += 1
        return JsonResponse({"value": calls})

    key = str(uuid.uuid4())
    view(_request(b'{"value":1}', key))
    response = view(_request(b'{"value":2}', key))
    payload = json.loads(response.content)

    assert calls == 1
    assert response.status_code == 409
    assert payload["error"]["code"] == IDEMPOTENCY_CONFLICT.code


def test_idempotent_request_replays_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: client)
    calls = 0

    @idempotent("test")
    def view(request: HttpRequest) -> HttpResponse:
        nonlocal calls
        calls += 1
        raise ApiError(IDEMPOTENCY_CONFLICT)

    key = str(uuid.uuid4())
    first = view(_request(b"{}", key))
    second = view(_request(b"{}", key))

    assert calls == 1
    assert first.status_code == second.status_code == 409
    assert first.content == second.content


def test_idempotent_concurrent_requests_execute_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: client)
    calls = 0
    lock = threading.Lock()

    @idempotent("test")
    def view(request: HttpRequest) -> HttpResponse:
        nonlocal calls
        with lock:
            calls += 1
        time.sleep(0.1)
        return JsonResponse({"value": "done"})

    key = str(uuid.uuid4())
    results: list[HttpResponse] = []

    def invoke() -> None:
        results.append(view(_request(b"{}", key)))

    threads = [threading.Thread(target=invoke) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert calls == 1
    assert results[0].content == results[1].content


def test_idempotent_get_bypasses_key() -> None:
    @idempotent("test")
    def view(request: HttpRequest) -> HttpResponse:
        return JsonResponse({"ok": True})

    request = RequestFactory().get("/test")

    assert view(request).status_code == 200


def test_idempotent_head_and_options_bypass_key() -> None:
    @idempotent("test")
    def view(request: HttpRequest) -> HttpResponse:
        return JsonResponse({"ok": True})

    head = RequestFactory().head("/test")
    options = RequestFactory().options("/test")

    assert view(head).status_code == 200
    assert view(options).status_code == 200


def test_idempotency_record_expiry_allows_reexecution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeRedis()
    monkeypatch.setattr("apps.common.idempotency.redis_client", lambda: client)
    calls = 0

    @idempotent("test")
    def view(request: HttpRequest) -> HttpResponse:
        nonlocal calls
        calls += 1
        return JsonResponse({"value": calls})

    key = str(uuid.uuid4())
    view(_request(b"{}", key))
    client.records.pop(f"idempotency:anonymous:test:{key}")
    response = view(_request(b"{}", key))
    payload = json.loads(response.content)

    assert calls == 2
    assert payload["value"] == 2


def test_write_without_idempotent_decorator_can_repeat() -> None:
    calls = 0

    def view(request: HttpRequest) -> HttpResponse:
        nonlocal calls
        calls += 1
        return JsonResponse({"value": calls})

    request = RequestFactory().post("/test", data=b"{}", content_type="application/json")

    assert view(request).status_code == 200
    assert view(request).status_code == 200
    assert calls == 2


def test_idempotent_invalid_key_is_rejected() -> None:
    @idempotent("test")
    def view(request: HttpRequest) -> HttpResponse:
        return JsonResponse({"ok": True})

    with pytest.raises(ApiError):
        view(_request(b"{}", "not-a-uuid"))
