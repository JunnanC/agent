"""Deterministic Fake RuntimeAdapter for G1 contract testing and CI smoke runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .contracts import (
    RuntimeAccess,
    RuntimeAdapter,
    RuntimeCapabilities,
    RuntimeError,
    RuntimeMetrics,
    RuntimeProgress,
    RuntimeResult,
    RuntimeSnapshot,
    RuntimeSpec,
    RuntimeStatus,
)
from .enums import InstanceStatus, RuntimeType


class FakeRuntimeAdapter(RuntimeAdapter):
    """In-memory adapter with deterministic IDs, progress, and failures.

    It is a contract fixture only and must not be represented as a production
    container or virtual-machine runtime.
    """

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.name = "fake"
        self.fail_on = fail_on
        self._runtimes: dict[str, dict[str, Any]] = {}
        self._creation_keys: dict[str, str] = {}
        self._destruction_results: dict[str, RuntimeResult] = {}

    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            runtime_type=RuntimeType.CONTAINER,
            access_modes=(
                "WEB_IDE",
                "NOTEBOOK",
                "WEB_TERMINAL",
                "WEB_PREVIEW",
                "REMOTE_DESKTOP",
            ),
            supports_snapshot=True,
            supports_stop=True,
            supports_metrics=True,
        )

    @staticmethod
    def _stable_id(kind: str, key: str) -> str:
        return f"fake-{kind}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:20]}"

    def _failure(self, error_code: str, retryable: bool) -> RuntimeError:
        return RuntimeError(error_code=error_code, message="Fake adapter failure", retryable=retryable)

    def validate_spec(self, spec: RuntimeSpec, *, idempotency_key: str) -> RuntimeResult:
        if not idempotency_key:
            return RuntimeResult(False, RuntimeError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency key is required", False), {})
        if self.fail_on == "validate_spec":
            return RuntimeResult(False, self._failure("FAKE_VALIDATION_FAILED", True), {})
        try:
            RuntimeSpec(**asdict(spec))
        except ValueError as exc:
            return RuntimeResult(False, RuntimeError(str(exc), "Runtime spec is invalid", False), {})
        return RuntimeResult(True, None, {"validated_runtime_type": spec.runtime_type.value})

    def create(self, spec: RuntimeSpec, *, idempotency_key: str) -> RuntimeResult:
        if not idempotency_key:
            return RuntimeResult(False, RuntimeError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency key is required", False), {})
        if self.fail_on == "create":
            return RuntimeResult(False, self._failure("FAKE_CREATE_FAILED", True), {})
        runtime_id = self._stable_id("instance", idempotency_key)
        previous = self._creation_keys.get(idempotency_key)
        replay = previous == runtime_id
        if not replay:
            self._creation_keys[idempotency_key] = runtime_id
            self._runtimes[runtime_id] = {
                "status": InstanceStatus.PROVISIONING,
                "progress_percent": 10,
                "spec": spec,
                "stopped": False,
            }
        return RuntimeResult(True, None, {"runtime_instance_id": runtime_id, "idempotent_replay": replay})

    def _runtime(self, runtime_instance_id: str) -> dict[str, Any]:
        runtime = self._runtimes.get(runtime_instance_id)
        if runtime is None:
            raise KeyError("RUNTIME_NOT_FOUND")
        return runtime

    def get_status(self, runtime_instance_id: str) -> RuntimeStatus:
        try:
            runtime = self._runtime(runtime_instance_id)
        except KeyError:
            return RuntimeStatus(runtime_instance_id, InstanceStatus.FAILED, False, RuntimeError("RUNTIME_NOT_FOUND", "Runtime not found", False))
        return RuntimeStatus(runtime_instance_id, runtime["status"])

    def get_progress(self, runtime_instance_id: str) -> RuntimeProgress:
        try:
            runtime = self._runtime(runtime_instance_id)
        except KeyError:
            return RuntimeProgress(0, "CREATE_RUNTIME", False, RuntimeError("RUNTIME_NOT_FOUND", "Runtime not found", False))
        return RuntimeProgress(runtime["progress_percent"], "CREATE_RUNTIME")

    def issue_access(self, runtime_instance_id: str, user_id: str, access_mode: str) -> RuntimeResult:
        try:
            runtime = self._runtime(runtime_instance_id)
        except KeyError:
            return RuntimeResult(False, RuntimeError("RUNTIME_NOT_FOUND", "Runtime not found", False), {})
        if runtime["status"] not in {InstanceStatus.READY, InstanceStatus.RUNNING}:
            return RuntimeResult(False, RuntimeError("RUNTIME_NOT_READY", "Runtime is not ready", False), {})
        if access_mode not in self.capabilities().access_modes:
            return RuntimeResult(False, RuntimeError("ACCESS_MODE_NOT_ALLOWED", "Access mode is not allowed", False), {})
        digest = hashlib.sha256(f"{runtime_instance_id}:{user_id}:{access_mode}".encode()).hexdigest()
        access = RuntimeAccess(
            access_url=f"https://workspace.invalid/{digest[:12]}",
            short_term_token=f"fake-token-{digest[:24]}",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            access_mode=access_mode,
        )
        return RuntimeResult(True, None, {"access": access})

    def snapshot(self, runtime_instance_id: str, policy: Mapping[str, Any]) -> RuntimeResult:
        try:
            self._runtime(runtime_instance_id)
        except KeyError:
            return RuntimeResult(False, RuntimeError("RUNTIME_NOT_FOUND", "Runtime not found", False), {})
        if self.fail_on == "snapshot":
            return RuntimeResult(False, self._failure("FAKE_SNAPSHOT_FAILED", True), {})
        digest = hashlib.sha256(json.dumps(dict(policy), sort_keys=True).encode()).hexdigest()
        snapshot = RuntimeSnapshot(snapshot_id=f"fake-snapshot-{digest[:20]}", digest=f"sha256:{digest}")
        return RuntimeResult(True, None, {"snapshot": snapshot})

    def stop(self, runtime_instance_id: str) -> RuntimeResult:
        try:
            runtime = self._runtime(runtime_instance_id)
        except KeyError:
            return RuntimeResult(False, RuntimeError("RUNTIME_NOT_FOUND", "Runtime not found", False), {})
        runtime["status"] = InstanceStatus.STOPPED
        runtime["stopped"] = True
        return RuntimeResult(True, None, {"status": InstanceStatus.STOPPED.value})

    def destroy(self, runtime_instance_id: str, *, idempotency_key: str) -> RuntimeResult:
        if not idempotency_key:
            return RuntimeResult(False, RuntimeError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency key is required", False), {})
        if runtime_instance_id in self._destruction_results:
            previous = self._destruction_results[runtime_instance_id]
            return RuntimeResult(True, None, {**previous.data, "idempotent_replay": True})
        if runtime_instance_id not in self._runtimes:
            result = RuntimeResult(True, None, {"status": InstanceStatus.DESTROYED.value, "idempotent_replay": True})
            self._destruction_results[runtime_instance_id] = result
            return result
        self._runtimes[runtime_instance_id]["status"] = InstanceStatus.DESTROYED
        result = RuntimeResult(True, None, {"status": InstanceStatus.DESTROYED.value, "idempotent_replay": False})
        self._destruction_results[runtime_instance_id] = result
        return result

    def collect_metrics(self, runtime_instance_id: str) -> RuntimeMetrics:
        self._runtime(runtime_instance_id)
        digest = hashlib.sha256(runtime_instance_id.encode()).hexdigest()
        return RuntimeMetrics(
            cpu_usage_percent=(int(digest[:2], 16) / 255) * 100,
            memory_usage_mib=int(digest[2:6], 16) % 1024,
            disk_usage_mib=int(digest[6:10], 16) % 4096,
            process_count=int(digest[10:12], 16) % 100,
        )






