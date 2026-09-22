from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import DatabaseError
from django.http import JsonResponse
from django.test import Client, RequestFactory

from apps.common.portal.middleware import PortalContextMiddleware
from apps.common.sse.enums import SSEEventType
from apps.common.sse.events import SSEEvent


@pytest.fixture
def portals(settings):
    settings.ALLOWED_HOSTS = ["user.example.edu", "teacher.example.edu", "admin.example.edu", "unknown.example.edu"]
    settings.PORTAL_HOST_MAP = {
        "user.example.edu": "USER", "teacher.example.edu": "TEACHING", "admin.example.edu": "PLATFORM"
    }
    settings.PORTAL_TRUST_PROXY_ENABLED = True
    settings.PORTAL_TRUSTED_PROXY_IPS = {"10.2.0.5"}
    settings.PORTAL_TRUSTED_PROXY_HOSTS = []


def portal_request(host, portal="USER", source="10.2.0.5"):
    request = RequestFactory().get(
        "/api/v1/me/membership", HTTP_HOST=host, HTTP_X_PORTAL=portal, REMOTE_ADDR=source
    )
    return PortalContextMiddleware(lambda req: JsonResponse({"portal": req.portal}))(request)


@pytest.mark.parametrize("host,portal", [
    ("user.example.edu", "USER"), ("teacher.example.edu", "TEACHING"), ("admin.example.edu", "PLATFORM")
])
def test_trusted_gateway_portals(portals, host, portal):
    assert portal_request(host, portal).status_code == 200


@pytest.mark.parametrize("host,portal,source,status", [
    ("unknown.example.edu", "USER", "10.2.0.5", 400),
    ("user.example.edu", "PLATFORM", "10.2.0.5", 403),
    ("user.example.edu", "", "10.2.0.5", 403),
    ("admin.example.edu", "PLATFORM", "203.0.113.8", 400),
])
def test_reject_unknown_forged_and_direct_requests(portals, host, portal, source, status):
    assert portal_request(host, portal, source).status_code == status


def test_gateway_dns_refresh_and_failure_closed(portals, settings):
    settings.PORTAL_TRUSTED_PROXY_IPS = set()
    settings.PORTAL_TRUSTED_PROXY_HOSTS = ["tasks.nginx"]
    with patch("apps.common.portal.middleware.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.2.0.5", 0))]):
        assert portal_request("user.example.edu").status_code == 200
    with patch("apps.common.portal.middleware.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.2.0.6", 0))]):
        assert portal_request("user.example.edu").status_code == 400


def test_local_host_cannot_be_overridden_by_header(portals, settings):
    settings.PORTAL_TRUST_PROXY_ENABLED = False
    assert portal_request("user.example.edu", "").status_code == 200
    assert portal_request("user.example.edu", "PLATFORM").status_code == 403


def test_liveness_needs_no_database():
    response = Client().get("/health/live", headers={"X-Trace-ID": "probe-trace"})
    assert response.status_code == 200
    assert response.json()["meta"]["trace_id"] == response["X-Trace-ID"] == "probe-trace"


@pytest.mark.django_db
def test_readiness_and_sanitized_failure():
    assert Client().get("/health/ready").status_code == 200
    with patch("apps.common.probes.views.connection.cursor", side_effect=DatabaseError("private SQL credential")):
        response = Client().get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["retryable"] is True
    assert "private" not in response.content.decode()


@pytest.mark.parametrize("path", ["/api/v1/schema/", "/api/v1/docs/", "/api/v1/redoc/", "/api/v1/platform/health"])
def test_sensitive_endpoints_not_public(path):
    assert Client().get(path).status_code == 403


def test_sse_event_wire_preserves_id_and_json_escaping():
    event = SSEEvent.create(
        event_type=next(iter(SSEEventType)), assignment_id=1, instance_id=2,
        operation_id=str(uuid4()), status="READY", message="line 1\nline 2",
        trace_id=str(uuid4()), progress_percent=100,
    )
    wire = event.to_wire()
    assert f"id:{event.event_id}" in wire
    assert wire.count("\n") == 4
    assert wire.endswith("\n\n")
    with pytest.raises(ValueError, match="PROGRESS_OUT_OF_RANGE"):
        SSEEvent(**{**event.payload(), "progress_percent": 101})
