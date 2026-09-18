from __future__ import annotations

from django.test import Client

from apps.common.errors import INVALID_ROLE

from .conftest import make_user


def test_admin_users_list_masks_phone_and_filters_deleted(
    roles: dict[str, object], active_membership: dict[str, str]
) -> None:
    admin = make_user(roles, username="admin", role_code="SYSTEM_ADMIN")
    make_user(roles, username="normal", role_code="USER")
    deleted = make_user(roles, username="deleted", role_code="USER")
    deleted.deleted_at = deleted.created_at
    deleted.save(update_fields=["deleted_at"])
    from apps.identity.services.auth import issue_access_token

    access, _ = issue_access_token(admin.id, "SYSTEM_ADMIN", "ACTIVE")
    response = Client().get(
        "/admin/users",
        headers={"Authorization": f"Bearer {access}"},
    )
    payload = response.json()
    assert "items" in payload.get("data", {}), payload
    payload = payload["data"]
    usernames = {item["username"] for item in payload["items"]}

    assert response.status_code == 200
    assert usernames == {"normal", "admin"}
    assert payload["items"][0]["phone"].startswith("+86")
    assert "****" in payload["items"][0]["phone"]


def test_create_user_rejects_non_builtin_role(roles: dict[str, object]) -> None:
    import pytest

    from apps.common.errors import ApiError
    from apps.identity.services.admin_users import create_user

    with pytest.raises(ApiError) as exc_info:
        create_user(
            1,
            {
                "username": "new_user",
                "password": "Password123",
                "email": "new@example.com",
                "role_id": 999,
            },
        )
    assert exc_info.value.error == INVALID_ROLE
