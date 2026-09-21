"""In-memory fakes for the B5 controlled-download skeleton."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FakeObjectAsset:
    public_id: str
    owner_user_id: str
    course_id: str
    retention_status: str
    allowed_uses: tuple[str, ...]
    course_participant_user_ids: tuple[str, ...]


@dataclass(frozen=True)
class IssuedDownloadGrant:
    asset_id: str
    one_time_token: str
    expires_at: datetime
    max_uses: int


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


class IdempotencyKeyInvalid(Exception):
    pass


class IdempotencyKeyConflict(Exception):
    pass


class IdempotencyStoreSaturated(Exception):
    pass


@dataclass(frozen=True)
class DownloadGrantResult:
    grant: IssuedDownloadGrant
    replayed: bool


@dataclass(frozen=True)
class StoredIdempotencySnapshot:
    actor_user_id: str
    idempotency_key: str
    fingerprint: str
    grant: IssuedDownloadGrant
    expires_at: datetime


class FakeObjectAssetRepository:
    def __init__(self) -> None:
        self.assets = {
            "asset-001": FakeObjectAsset(
                public_id="asset-001",
                owner_user_id="42",
                course_id="course-001",
                retention_status="RETAINED",
                allowed_uses=("REPORT_DOWNLOAD",),
                course_participant_user_ids=("42",),
            )
        }

    def get(self, asset_id: str) -> FakeObjectAsset | None:
        return self.assets.get(asset_id)

    def reset(self) -> None:
        self.__init__()


class FakeIdempotencyRepository:
    """Process-local idempotency snapshots, separate from grant storage."""

    def __init__(self, lock: threading.RLock) -> None:
        self.records: dict[tuple[str, str], StoredIdempotencySnapshot] = {}
        self.lock = lock

    def sweep(self, now: datetime) -> None:
        with self.lock:
            expired = [
                key
                for key, snapshot in self.records.items()
                if now >= snapshot.expires_at
            ]
            for key in expired:
                del self.records[key]

    def save(self, snapshot: StoredIdempotencySnapshot) -> None:
        with self.lock:
            self.records[(snapshot.actor_user_id, snapshot.idempotency_key)] = snapshot

    def reset(self) -> None:
        with self.lock:
            self.records.clear()


class FakeDownloadGrantRepository:
    """Store grants by token hash, never by plaintext token."""

    def __init__(self) -> None:
        self.grants: dict[str, StoredDownloadGrant] = {}
        self.lock = threading.RLock()

    def save(self, grant: StoredDownloadGrant) -> None:
        with self.lock:
            self.grants[grant.token_hash] = grant

    def get_by_hash(self, token_hash: str) -> StoredDownloadGrant | None:
        with self.lock:
            return self.grants.get(token_hash)

    def consume(self, token_hash: str) -> StoredDownloadGrant | None:
        with self.lock:
            grant = self.grants.get(token_hash)
            if grant is None or grant.used_count >= grant.max_uses:
                return None
            grant.used_count += 1
            return grant

    def reset(self) -> None:
        with self.lock:
            self.grants.clear()


class FakeObjectAssetScopeSelector:
    def can_access(self, *, asset, actor_user_id, portal, course_id, use) -> bool:
        return (
            portal in {"USER", "TEACHING", "PLATFORM"}
            and course_id == asset.course_id
            and use in asset.allowed_uses
            and actor_user_id in asset.course_participant_user_ids
        )


FAKE_OBJECT_ASSET_REPOSITORY = FakeObjectAssetRepository()
FAKE_DOWNLOAD_GRANT_REPOSITORY = FakeDownloadGrantRepository()
FAKE_IDEMPOTENCY_REPOSITORY = FakeIdempotencyRepository(
    FAKE_DOWNLOAD_GRANT_REPOSITORY.lock
)
FAKE_OBJECT_ASSET_SCOPE_SELECTOR = FakeObjectAssetScopeSelector()

IDEMPOTENCY_KEY_PATTERN = re.compile(r"[\x20-\x7e]{1,255}")
IDEMPOTENCY_STORE_MAX_RECORDS = 10000
DOWNLOAD_GRANT_TTL_SECONDS = 120


def _idempotency_fingerprint(*, asset_id: str, use: str, portal: str) -> str:
    canonical_request = json.dumps(
        {"asset_id": asset_id, "portal": portal, "use": use},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()


def issue_fake_download_grant(
    *,
    actor_user_id: str,
    portal: str,
    asset_id: str,
    use: str,
    idempotency_key: str,
) -> DownloadGrantResult:
    if IDEMPOTENCY_KEY_PATTERN.fullmatch(idempotency_key) is None:
        raise IdempotencyKeyInvalid

    fingerprint = _idempotency_fingerprint(
        asset_id=asset_id,
        use=use,
        portal=portal,
    )
    with FAKE_DOWNLOAD_GRANT_REPOSITORY.lock:
        now = datetime.now(timezone.utc)
        FAKE_IDEMPOTENCY_REPOSITORY.sweep(now)
        snapshot = FAKE_IDEMPOTENCY_REPOSITORY.records.get(
            (actor_user_id, idempotency_key)
        )
        if snapshot is not None:
            if snapshot.fingerprint != fingerprint:
                raise IdempotencyKeyConflict
            logger.info(
                "download grant idempotently replayed",
                extra={"action": "download_grant_issued", "result": "replayed"},
            )
            return DownloadGrantResult(snapshot.grant, replayed=True)

        if (
            len(FAKE_IDEMPOTENCY_REPOSITORY.records)
            >= IDEMPOTENCY_STORE_MAX_RECORDS
        ):
            raise IdempotencyStoreSaturated

        asset = FAKE_OBJECT_ASSET_REPOSITORY.get(asset_id)
        if asset is None or asset.retention_status != "RETAINED":
            raise ValueError("RESOURCE_NOT_FOUND")
        if use not in asset.allowed_uses:
            raise ValueError("USE_NOT_ALLOWED")
        if not FAKE_OBJECT_ASSET_SCOPE_SELECTOR.can_access(
            asset=asset,
            actor_user_id=actor_user_id,
            portal=portal,
            course_id=asset.course_id,
            use=use,
        ):
            raise PermissionError("SCOPE_DENIED")

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=DOWNLOAD_GRANT_TTL_SECONDS
        )
        issued_grant = IssuedDownloadGrant(
            asset_id=asset.public_id,
            one_time_token=token,
            expires_at=expires_at,
            max_uses=1,
        )
        FAKE_DOWNLOAD_GRANT_REPOSITORY.save(
            StoredDownloadGrant(
                grant_id=str(uuid.uuid4()),
                token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                asset_id=asset.public_id,
                actor_user_id=actor_user_id,
                portal=portal,
                course_id=asset.course_id,
                use=use,
                expires_at=expires_at,
                max_uses=1,
            )
        )
        FAKE_IDEMPOTENCY_REPOSITORY.save(
            StoredIdempotencySnapshot(
                actor_user_id=actor_user_id,
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                grant=issued_grant,
                expires_at=expires_at,
            )
        )
        logger.info(
            "download grant issued",
            extra={"action": "download_grant_issued", "result": "created"},
        )
        return DownloadGrantResult(issued_grant, replayed=False)
