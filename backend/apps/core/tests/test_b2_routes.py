import json
from ipaddress import ip_network

from django.test import SimpleTestCase, override_settings


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

    def test_workspace_session_requires_idempotency_key(self):
        response = self.request("post", "/api/v2/tasks/task-001/workspace-sessions")
        self.assert_error_envelope(response, 400, "IDEMPOTENCY_KEY_REQUIRED")

    def test_workspace_routes_are_b4_placeholders(self):
        requests = [
            ("post", "/api/v2/tasks/task-001/workspace-sessions", "key-1"),
            ("post", "/api/v2/workspace-sessions/session-001/renew", "key-2"),
            ("post", "/api/v2/workspace-sessions/session-001/revoke", "key-3"),
            ("put", "/api/v2/tasks/task-001/workspace-snapshot", None),
        ]
        for method, path, key in requests:
            headers = {"HTTP_IDEMPOTENCY_KEY": key} if key else {}
            response = self.request(method, path, extra=headers)
            self.assert_error_envelope(response, 501, "NOT_IMPLEMENTED")

    def test_event_stream_is_b3_placeholder(self):
        response = self.request("get", "/api/v2/events/stream")
        self.assert_error_envelope(response, 501, "NOT_IMPLEMENTED")

    def test_internal_verify_from_untrusted_source_is_404(self):
        response = self.client.post(
            "/internal/workspace-tokens/verify",
            REMOTE_ADDR="203.0.113.10",
        )
        self.assert_error_envelope(response, 404, "NOT_FOUND")

    def test_internal_verify_from_trusted_source_is_b4_placeholder(self):
        response = self.client.post(
            "/internal/workspace-tokens/verify",
            REMOTE_ADDR="127.0.0.1",
        )
        self.assert_error_envelope(response, 501, "NOT_IMPLEMENTED")

    def test_forbidden_route_variants_are_404(self):
        for path in [
            "/events",
            "/api/v2/files/token-001",
            "/workspace/session-001",
            "/api/v2/me/experiment-tasks",
        ]:
            response = self.request("get", path)
            self.assert_error_envelope(response, 404, "NOT_FOUND")
