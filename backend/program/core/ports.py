"""Ports for core object-asset dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ObjectAssetScopeSelector(Protocol):
    """Domain-provided selector for object-level access."""

    def can_access(
        self,
        *,
        asset: Any,
        actor_user_id: str,
        portal: str,
        course_id: str,
        use: str,
    ) -> bool:
        """Return whether the actor can access the object now."""


@dataclass(frozen=True)
class VirusScanRequest:
    asset_id: str
    filename: str
    size: int
    content_type: str


@dataclass(frozen=True)
class VirusScanReceipt:
    scan_id: str
    status: "QUEUED"


@dataclass(frozen=True)
class VirusScanResult:
    scan_id: str
    status: str
    finding: str | None = None


class VirusScanPort(Protocol):
    """Reserved ClamAV upload-scan port.

    The production adapter must enqueue a scan and immediately return a QUEUED
    receipt. The upload route then responds asynchronously with 202 while a
    worker obtains the final result; objects must not become business-visible
    before the scan is CLEAN. This port is intentionally not implemented in
    slice B5.
    """

    def enqueue_scan(self, request: VirusScanRequest) -> VirusScanReceipt:
        """Queue a scan without scanning in the web request."""

    def get_scan_result(self, scan_id: str) -> VirusScanResult:
        """Return the latest immutable scan result."""
