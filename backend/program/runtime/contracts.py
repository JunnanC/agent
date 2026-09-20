"""Immutable contracts and the nine-method ``RuntimeAdapter`` interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from .enums import InstanceStatus, RuntimeType


@dataclass(frozen=True, slots=True)
class RuntimeSpec:
    """Server-composed runtime specification.

    User requests must never populate this object directly. The orchestration
    service composes it from a frozen template version, task policy, quota,
    whitelist, and security policy.
    """

    runtime_type: RuntimeType
    image_digest: str
    cpu_limit: float
    memory_limit_mib: int
    disk_limit_mib: int
    process_limit: int
    execution_timeout_seconds: int
    network_enabled: bool = False
    mounted_materials: tuple[str, ...] = ()
    environment: Mapping[str, str] = field(default_factory=dict)
    cloud_init: Mapping[str, str] = field(default_factory=dict)
    allowed_access_modes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.runtime_type not in RuntimeType:
            raise ValueError("RUNTIME_TYPE_INVALID")
        if not self.image_digest:
            raise ValueError("IMAGE_REQUIRED")
        if self.cpu_limit <= 0 or self.memory_limit_mib <= 0 or self.disk_limit_mib <= 0:
            raise ValueError("RESOURCE_LIMIT_INVALID")
        if self.process_limit <= 0 or self.execution_timeout_seconds <= 0:
            raise ValueError("RESOURCE_LIMIT_INVALID")
        if self.network_enabled:
            # The baseline default is deny; enabling network requires a policy flag
            # supplied by the server-side policy engine, never by a user request.
            if not self.environment.get("X_RUNTIME_NETWORK_POLICY"):
                raise ValueError("NETWORK_POLICY_REQUIRED")


@dataclass(frozen=True, slots=True)
class RuntimeError:
    """Stable, non-sensitive adapter error."""

    error_code: str
    message: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class RuntimeCapabilities:
    runtime_type: RuntimeType
    access_modes: tuple[str, ...]
    supports_snapshot: bool
    supports_stop: bool
    supports_metrics: bool


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    ok: bool
    error: RuntimeError | None = None
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeStatus:
    runtime_instance_id: str
    status: InstanceStatus
    retryable: bool = False
    error: RuntimeError | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeProgress:
    progress_percent: int
    stage: str
    retryable: bool = False
    error: RuntimeError | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0 <= self.progress_percent <= 100:
            raise ValueError("PROGRESS_OUT_OF_RANGE")


@dataclass(frozen=True, slots=True)
class RuntimeAccess:
    access_url: str
    short_term_token: str
    expires_at: datetime
    access_mode: str


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    snapshot_id: str
    digest: str


@dataclass(frozen=True, slots=True)
class RuntimeMetrics:
    cpu_usage_percent: float
    memory_usage_mib: float
    disk_usage_mib: float
    process_count: int


class RuntimeAdapter(ABC):
    """Contract shared by container, virtual machine, and fake adapters.

    The nine method names are frozen by the baseline. ``validate_spec`` and
    ``create`` both receive an idempotency key; ``destroy`` also uses one so
    repeated calls converge to the same terminal result.
    """

    name: str = "runtime_adapter"

    @abstractmethod
    def capabilities(self) -> RuntimeCapabilities:
        """Return adapter capability metadata (not one of the nine operations)."""

    @abstractmethod
    def validate_spec(
        self, spec: RuntimeSpec, *, idempotency_key: str
    ) -> RuntimeResult:
        """Validate a server-composed spec using a stable idempotency key."""

    @abstractmethod
    def create(self, spec: RuntimeSpec, *, idempotency_key: str) -> RuntimeResult:
        """Create an external runtime and return its external resource ID."""

    @abstractmethod
    def get_status(self, runtime_instance_id: str) -> RuntimeStatus:
        """Return the adapter fact status for an external resource."""

    @abstractmethod
    def get_progress(self, runtime_instance_id: str) -> RuntimeProgress:
        """Return deterministic stage progress for an external resource."""

    @abstractmethod
    def issue_access(
        self, runtime_instance_id: str, user_id: str, access_mode: str
    ) -> RuntimeResult:
        """Issue a revocable short-term workspace access credential."""

    @abstractmethod
    def snapshot(
        self, runtime_instance_id: str, policy: Mapping[str, Any]
    ) -> RuntimeResult:
        """Create a snapshot according to the server-approved policy."""

    @abstractmethod
    def stop(self, runtime_instance_id: str) -> RuntimeResult:
        """Stop a running runtime without deleting it."""

    @abstractmethod
    def destroy(
        self, runtime_instance_id: str, *, idempotency_key: str
    ) -> RuntimeResult:
        """Destroy a runtime idempotently and return the terminal result."""

    @abstractmethod
    def collect_metrics(self, runtime_instance_id: str) -> RuntimeMetrics:
        """Collect resource metrics for monitoring and quota reconciliation."""
