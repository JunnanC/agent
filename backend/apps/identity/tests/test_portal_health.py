import pytest
from django.test import Client

from apps.identity.services.auth import issue_access_token

from .conftest import make_user


@pytest.mark.parametrize("role,portal,expected", [
    ("SYSTEM_ADMIN", "PLATFORM", 200),
    ("SYSTEM_ADMIN", "USER", 403),
    ("ORG_ADMIN", "PLATFORM", 403),
    ("USER", "PLATFORM", 403),
])
def test_health_requires_both_portal_and_real_identity(roles, active_membership, settings, role, portal, expected):
    settings.PORTAL_HOST_MAP = {"testserver": portal}
    user = make_user(roles, username="health-user", role_code=role)
    token, _ = issue_access_token(user.id, role, "ACTIVE")
    response = Client().get("/api/v1/platform/health", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == expected
    if expected == 200:
        assert response.json()["data"]["checks"]["database"] == "ok"


def test_docs_accept_existing_admin_token(roles, active_membership, settings):
    settings.PORTAL_HOST_MAP = {"testserver": "PLATFORM"}
    user = make_user(roles, username="docs-admin", role_code="SYSTEM_ADMIN")
    token, _ = issue_access_token(user.id, "SYSTEM_ADMIN", "ACTIVE")
    response = Client().get("/api/v1/docs/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
