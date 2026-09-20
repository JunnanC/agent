"""In-memory fakes for the B5 object download skeleton."""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class FakeObjectAsset:
    public_id: str
    owner_user_id: str
    course_id: str
    retention_status: str
    allowed_uses: Iterable[str]
    course_participant_user_ids: Iterable[str]


class FakeObjectAssetRepository:
    def __init__(self) -> None:
        self._assets = {
            "asset-report-001": FakeObjectAsset(
                public_id="asset-report-001",
                owner_user_id="42",
                course_id="course-001",
                retention_status="RETAINED",
                allowed_uses=("REPORT_DOWNLOAD",),
                course_participant_user_ids=("42", "43"),
            )
        }

    def get(self, asset_id: str) -> FakeObjectAsset | None:
        return self._assets.get(asset_id)

    def reset(self) -> None:
        self.__init__()


@dataclass
class StoredDownloadGrant:
    grant_id: str
    token_hash: str
    asset_id: str
    actor_user_id: str
    portal: str
    course_id: str
    use: str
    expires_at: datetime
    max_uses: int
    used_count: int = 0


class FakeDownloadGrantRepository:
    """Store grants by SHA-256 token hash, never by plaintext token."""

    def __init__(self) -> None:
        self.grants: dict[str, StoredDownloadGrant] = {}
        self._lock = threading.RLock()

    def save(self, grant: StoredDownloadGrant) -> None:
        with self._lock:
            self.grants[grant.token_hash] = grant

    def get_by_hash(self, token_hash: str) -> StoredDownloadGrant | None:
        with self._lock:
            grant = self.grants.get(token_hash)
            return replace(grant) if grant else None

    def consume(self, token_hash: str) -> StoredDownloadGrant | None:
        with self._lock:
            grant = self.grants.get(token_hash)
            if grant is None or grant.used_count >= grant.max_uses:
                return None
            consumed = replace(grant, used_count=grant.used_count + 1)
            self.grants[token_hash] = consumed
            return consumed

    def reset(self) -> None:
        self.__init__()


class FakeObjectAssetScopeSelector:
    """Fake selector standing in for the future courses-domain selector."""

    def can_access(self, *, asset, actor_user_id, portal, course_id, use) -> bool:
        actor_in_course = actor_user_id in asset.course_participant_user_ids
        return (
            portal in {"USER", "TEACHER", "ADMIN"}
            and course_id == asset.course_id
            and use in asset.allowed_uses
            and (actor_user_id == asset.owner_user_id or actor_in_course)
        )


FAKE_OBJECT_ASSET_REPOSITORY = FakeObjectAssetRepository()
FAKE_DOWNLOAD_GRANT_REPOSITORY = FakeDownloadGrantRepository()
FAKE_OBJECT_ASSET_SCOPE_SELECTOR = FakeObjectAssetScopeSelector()
