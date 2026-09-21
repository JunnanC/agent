from __future__ import annotations

from apps.common.providers import PermissionDecision

from .conftest import grant_permission, make_user


def test_permission_matrix_rejects_unauthorized_scope(
    roles: dict[str, object], active_membership: dict[str, str]
) -> None:
    grant_permission(roles["USER"], "identity:read", "IDENTITY")
    user = make_user(roles, username="user", role_code="USER")
    from apps.identity.services.permissions import (
        IdentityPrincipalPermissionProvider,
        resolve_scope,
    )

    decision = IdentityPrincipalPermissionProvider().get_permission(str(user.id), "identity:read")
    assert decision == PermissionDecision(allowed=True, scope="SELF")
    assert resolve_scope(user, "identity:read") == "SELF"


def test_unverified_runtime_action_is_denied(roles: dict[str, object], monkeypatch: object) -> None:
    grant_permission(roles["USER"], "runtime:start", "RUNTIME")
    user = make_user(roles, username="unverified")
    monkeypatch.setattr(
        "apps.identity.services.permissions.get_membership",
        lambda _user_id: {"membership_id": "membership-1", "status": "ACTIVE"},
    )
    monkeypatch.setattr(
        "apps.identity.services.permissions.membership_service",
        lambda: type(
            "Service",
            (),
            {"unverified_start_policy": lambda _self, _membership_id: "DENIED"},
        )(),
    )

    from apps.identity.services.permissions import IdentityPrincipalPermissionProvider

    decision = IdentityPrincipalPermissionProvider().get_permission(str(user.id), "runtime:start")
    assert decision.allowed is False
    assert decision.scope == "NONE"
