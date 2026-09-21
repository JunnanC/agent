from __future__ import annotations

from typing import Protocol

from django.conf import settings
from django.utils.module_loading import import_string


class AuthorizedScopeProvider(Protocol):
    def authorized_user_ids(self, actor_id: int) -> set[int]: ...


class EmptyAuthorizedScopeProvider:
    def authorized_user_ids(self, actor_id: int) -> set[int]:
        return set()


def authorized_scope_provider() -> AuthorizedScopeProvider:
    path = getattr(settings, "MEMBERSHIP_AUTHORIZED_SCOPE_PROVIDER", "")
    if not path:
        return EmptyAuthorizedScopeProvider()
    provider = import_string(path)
    return provider() if isinstance(provider, type) else provider
