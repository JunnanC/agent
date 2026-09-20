"""Use cases for core object-asset controlled downloads."""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core.adapters.fake import (
    FAKE_DOWNLOAD_GRANT_REPOSITORY,
    FAKE_OBJECT_ASSET_REPOSITORY,
    FAKE_OBJECT_ASSET_SCOPE_SELECTOR,
    StoredDownloadGrant,
)

logger = logging.getLogger(__name__)


class ObjectAssetNotFound(Exception):
    pass


class PortalRequired(Exception):
    pass


class DownloadDenied(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


@dataclass(frozen=True)
class IssuedDownloadGrant:
    asset_id: str
    one_time_token: str
    expires_at: datetime
    max_uses: int


@dataclass(frozen=True)
class ExchangedDownloadGrant:
    grant_id: str
    asset_id: str
    use: str


class DownloadGrantService:
    def __init__(
        self,
        asset_repository=FAKE_OBJECT_ASSET_REPOSITORY,
        grant_repository=FAKE_DOWNLOAD_GRANT_REPOSITORY,
        scope_selector=FAKE_OBJECT_ASSET_SCOPE_SELECTOR,
        token_ttl_seconds: int = 120,
    ) -> None:
        self.asset_repository = asset_repository
        self.grant_repository = grant_repository
        self.scope_selector = scope_selector
        self.token_ttl_seconds = token_ttl_seconds

    def issue(
        self,
        *,
        actor_user_id: str,
        portal: str | None,
        asset_id: str,
        use: str,
    ) -> IssuedDownloadGrant:
        if not portal:
            raise PortalRequired()

        asset = self.asset_repository.get(asset_id)
        if asset is None:
            raise ObjectAssetNotFound()
        if asset.retention_status != "RETAINED":
            raise DownloadDenied("RETENTION_BLOCKED")
        if use not in asset.allowed_uses:
            raise DownloadDenied("USE_NOT_ALLOWED")
        if not self.scope_selector.can_access(
            asset=asset,
            actor_user_id=actor_user_id,
            portal=portal,
            course_id=asset.course_id,
            use=use,
        ):
            raise DownloadDenied("SCOPE_DENIED")

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=self.token_ttl_seconds,
        )
        stored_grant = StoredDownloadGrant(
            grant_id=str(uuid.uuid4()),
            token_hash=token_hash,
            asset_id=asset.public_id,
            actor_user_id=actor_user_id,
            portal=portal,
            course_id=asset.course_id,
            use=use,
            expires_at=expires_at,
            max_uses=1,
        )
        self.grant_repository.save(stored_grant)
        logger.info(
            "Controlled download grant issued",
            extra={"asset_id": asset.public_id, "grant_id": stored_grant.grant_id},
        )
        return IssuedDownloadGrant(
            asset_id=asset.public_id,
            one_time_token=token,
            expires_at=expires_at,
            max_uses=stored_grant.max_uses,
        )

    def exchange(self, *, one_time_token: str) -> ExchangedDownloadGrant:
        token_hash = hashlib.sha256(one_time_token.encode("utf-8")).hexdigest()
        grant = self.grant_repository.get_by_hash(token_hash)
        if grant is None:
            raise DownloadDenied("INVALID_TOKEN")
        if datetime.now(timezone.utc) >= grant.expires_at:
            raise DownloadDenied("TOKEN_EXPIRED")

        asset = self.asset_repository.get(grant.asset_id)
        if asset is None or asset.retention_status != "RETAINED":
            raise DownloadDenied("RETENTION_BLOCKED")
        if not self.scope_selector.can_access(
            asset=asset,
            actor_user_id=grant.actor_user_id,
            portal=grant.portal,
            course_id=grant.course_id,
            use=grant.use,
        ):
            raise DownloadDenied("SCOPE_DENIED")

        consumed = self.grant_repository.consume(token_hash)
        if consumed is None:
            raise DownloadDenied("TOKEN_USES_EXHAUSTED")
        logger.info(
            "Controlled download grant accepted",
            extra={"asset_id": consumed.asset_id, "grant_id": consumed.grant_id},
        )
        return ExchangedDownloadGrant(
            grant_id=consumed.grant_id,
            asset_id=consumed.asset_id,
            use=consumed.use,
        )


download_grant_service = DownloadGrantService()
