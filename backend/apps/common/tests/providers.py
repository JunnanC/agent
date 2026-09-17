from __future__ import annotations

from django.http import HttpRequest

from apps.common.providers import PermissionDecision


class PrincipalPermissionProvider:
    def get_permission(self, actor_user_id: str, action: str) -> PermissionDecision:
        return PermissionDecision(
            allowed=True,
            scope="SELF",
            object_ids=frozenset({actor_user_id}) if action == "me" else None,
        )


class SystemAdminActorProvider:
    def get_actor(self, request: HttpRequest) -> tuple[str | None, str | None]:
        return "1", "SYSTEM_ADMIN"


class UserActorProvider:
    def get_actor(self, request: HttpRequest) -> tuple[str | None, str | None]:
        return "2", "USER"
