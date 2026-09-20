import json
from ipaddress import ip_network

from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.core.adapters.fake import FAKE_DOWNLOAD_GRANT_REPOSITORY
from apps.core.views import DownloadGrantView


@override_settings(
    ALLOWED_HOSTS=["testserver", "user.localhost"],
    PORTAL_TRUSTED_PROXY_NETWORKS=[ip_network("127.0.0.0/8")],
    PORTAL_HOST_MAP={"USER": ["user.localhost"]},
)
class B2RouteTests(SimpleTestCase):
    def request(self, method, path, **kwargs):
        headers = {
            "HTTP_HOST": "user.localhost",
            "HTTP_X_PORTAL": "USER",
            "REMOTE_ADDR": "127.0.0.1",
        }
        headers.update(kwargs.pop("extra", {}))
        return getattr(self.client, method)(path, **kwargs, **headers)

    def assert_error_envelope(self, response, status_code, code):
        self.assertEqual(response.status_code, status_code)
        payload = json.loads(response.content)
        self.assertEqual(
            set(payload),
            {"code", "message", "details", "trace_id"},
        )
        self.assertEqual(payload["code"], code)
        self.assertTrue(payload["trace_id"])

    def test_health_is_exact_top_level_path(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["status"], "ok")

    def test_top_level_file_download_is_b5_placeholder(self):
        response = self.request("get", "/files/token-001")
        self.assert_error_envelope(response, 501, "NOT_IMPLEMENTED")
        self.assertEqual(
            json.loads(response.content)["details"],
            {"slice": "B5", "route": "/files/token-001"},
        )

    def test_download_grants_requires_idempotency_key(self):
        response = self.request("post", "/api/v2/files/asset-001/download-grants")
        self.assert_error_envelope(response, 400, "IDEMPOTENCY_KEY_REQUIRED")

    def test_download_grants_issues_placeholder_token(self):
        factory = APIRequestFactory(enforce_csrf_checks=True)
        request = factory.post(
            "/api/v2/files/asset-001/download-grants",
            data={"use": "REPORT_DOWNLOAD"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="key-download-grant",
        )
        request.user = User(id=42, username="student-42")
        request.portal = "USER"
        csrf_token = get_token(request)
        request.COOKIES["csrftoken"] = csrf_token
        request.META["HTTP_X_CSRFTOKEN"] = csrf_token
        response = DownloadGrantView.as_view()(request, asset_id="asset-001")
        response.render()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        payload = json.loads(response.content)
        self.assertEqual(
            set(payload),
            {"asset_id", "one_time_token", "expires_at", "max_uses"},
        )
        self.assertTrue(payload["one_time_token"])
        self.assertEqual(payload["max_uses"], 1)
        stored = list(FAKE_DOWNLOAD_GRANT_REPOSITORY.grants.values())[-1]
        self.assertNotIn(payload["one_time_token"], repr(stored))
        self.assertEqual(len(stored.token_hash), 64)

    def test_workspace_session_requires_idempotency_key(self):
        response = self.request("post", "/api/v2/tasks/task-001/workspace-sessions")
        self.assert_error_envelope(response, 400, "IDEMPOTENCY_KEY_REQUIRED")

    def test_workspace_routes_are_registered(self):
        response = self.request(
            "post",
            "/api/v2/tasks/task-001/workspace-sessions",
            data={"student_public_id": "student-001", "instance_public_id": "instance-001"},
            content_type="application/json",
            extra={"HTTP_IDEMPOTENCY_KEY": "key-1"},
        )
        self.assertEqual(response.status_code, 201)

        response = self.request(
            "put",
            "/api/v2/tasks/task-001/workspace-snapshot",
            data={"client_seq": 1},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_event_stream_is_sse(self):
        response = self.request("get", "/api/v2/events/stream")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "text/event-stream")

    def test_internal_verify_from_untrusted_source_is_404(self):
        response = self.client.post(
            "/internal/workspace-tokens/verify",
            REMOTE_ADDR="203.0.113.10",
        )
        self.assert_error_envelope(response, 404, "NOT_FOUND")

    def test_internal_verify_from_trusted_source_is_implemented(self):
        response = self.client.post(
            "/internal/workspace-tokens/verify",
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(response.status_code, 400)

    def test_forbidden_route_variants_are_404(self):
        for path in [
            "/events",
            "/api/v2/files/token-001",
            "/workspace/session-001",
            "/api/v2/me/experiment-tasks",
        ]:
            response = self.request("get", path)
            self.assert_error_envelope(response, 404, "NOT_FOUND")
