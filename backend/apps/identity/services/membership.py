from __future__ import annotations

from typing import Protocol

from django.conf import settings
from django.utils.module_loading import import_string


class MembershipService(Protocol):
    def get_membership(self, user_id: int) -> dict[str, str] | None: ...

    def unverified_start_policy(self, membership_id: str) -> str: ...

    def revoke_authentication_sessions(self, user_id: int) -> None: ...


class DeniedMembershipService:
    def get_membership(self, user_id: int) -> dict[str, str] | None:
        return None

    def unverified_start_policy(self, membership_id: str) -> str:
        return "DENIED"

    def revoke_authentication_sessions(self, user_id: int) -> None:
        return None


def membership_service() -> MembershipService:
    path = getattr(settings, "IDENTITY_MEMBERSHIP_PROVIDER", "")
    if not path:
        return DeniedMembershipService()
    provider = import_string(path)
    return provider() if isinstance(provider, type) else provider


def get_membership(user_id: int) -> dict[str, str] | None:
    return membership_service().get_membership(user_id)
