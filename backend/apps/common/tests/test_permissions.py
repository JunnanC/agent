from __future__ import annotations

import pytest
from django.http import HttpRequest
from django.test import override_settings

from apps.common.errors import ApiError
from apps.common.permissions import ROLE_MATRIX, require_route_permission, require_system_admin
from apps.common.providers import load_provider, principal_permission


def test_role_matrix_matches_spec() -> None:
    assert ROLE_MATRIX["USER"] == {"me": "SELF", "teaching": "NONE", "admin": "NONE"}
    assert ROLE_MATRIX["ORG_SUB_ADMIN"] == {
        "me": "SELF",
        "teaching": "AUTHORIZED",
        "admin": "NONE",
    }
    assert ROLE_MATRIX["ORG_ADMIN"] == {"me": "SELF", "teaching": "ALL", "admin": "NONE"}
    assert ROLE_MATRIX["SYSTEM_ADMIN"] == {"me": "SELF", "teaching": "NONE", "admin": "ALL"}


@override_settings(COMMON_AUDITABLE_ACTOR_PROVIDER="apps.common.tests.providers.UserActorProvider")
def test_user_cannot_access_admin_route() -> None:
    with pytest.raises(ApiError):
        require_route_permission(HttpRequest(), "admin")


@override_settings(
    COMMON_AUDITABLE_ACTOR_PROVIDER="apps.common.tests.providers.SystemAdminActorProvider"
)
def test_system_admin_can_access_admin_route() -> None:
    assert require_route_permission(HttpRequest(), "admin") == "ALL"


@override_settings(COMMON_AUDITABLE_ACTOR_PROVIDER="apps.common.tests.providers.UserActorProvider")
def test_require_system_admin_rejects_non_admin() -> None:
    with pytest.raises(ApiError):
        require_system_admin(HttpRequest())


@override_settings(
    COMMON_PRINCIPAL_PERMISSION_PROVIDER=("apps.common.tests.providers.PrincipalPermissionProvider")
)
def test_load_provider_instantiates_class_from_settings() -> None:
    provider = load_provider("COMMON_PRINCIPAL_PERMISSION_PROVIDER")

    assert provider is not None
    assert principal_permission("1", "me").scope == "SELF"


@override_settings(COMMON_PRINCIPAL_PERMISSION_PROVIDER="")
def test_missing_principal_permission_provider_returns_internal_error() -> None:
    with pytest.raises(ApiError) as exc_info:
        principal_permission("1", "me")

    assert exc_info.value.error.code == 50001


@override_settings(COMMON_PRINCIPAL_PERMISSION_PROVIDER="apps.common.tests.providers.Missing")
def test_invalid_principal_permission_provider_returns_internal_error() -> None:
    with pytest.raises(ApiError) as exc_info:
        load_provider("COMMON_PRINCIPAL_PERMISSION_PROVIDER")

    assert exc_info.value.error.code == 50001
