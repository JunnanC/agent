import yaml
from django.test import Client, TestCase


class HealthTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_liveness_returns_release_metadata_and_trace_id(self) -> None:
        response = self.client.get("/api/v2/health")

        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ok"
        assert response.json()["meta"]["trace_id"] == response["X-Request-ID"]
        assert response.json()["data"]["portal"] is None

    def test_liveness_reports_the_trusted_gateway_portal(self) -> None:
        response = self.client.get(
            "/api/v2/health",
            HTTP_X_PORTAL="USER",
            HTTP_X_PROXY_CONTEXT="ingress-v1",
        )

        assert response.status_code == 200
        assert response.json()["data"]["portal"] == "USER"

    def test_w3c_trace_id_is_propagated(self) -> None:
        trace_id = "4f9a2c1b7e3d6a804f9a2c1b7e3d6a80"
        response = self.client.get(
            "/api/v2/health",
            HTTP_TRACEPARENT=f"00-{trace_id}-4f9a2c1b7e3d6a80-01",
        )

        assert response["X-Request-ID"] == trace_id
        assert response.json()["meta"]["trace_id"] == trace_id

    def test_browser_api_requires_trusted_proxy_context(self) -> None:
        response = self.client.get("/api/v2/events/stream", HTTP_X_PORTAL="USER")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PROXY_CONTEXT_UNTRUSTED"

    def test_browser_api_accepts_gateway_portal(self) -> None:
        response = self.client.get(
            "/api/v2/events/stream",
            HTTP_X_PORTAL="USER",
            HTTP_X_PROXY_CONTEXT="ingress-v1",
        )

        assert response.status_code == 200
        assert response["X-Accel-Buffering"] == "no"

    def test_machine_context_cannot_access_browser_namespace(self) -> None:
        response = self.client.get(
            "/api/v2/events/stream",
            HTTP_X_AUTH_CONTEXT="INTEGRATION",
            HTTP_X_PROXY_CONTEXT="ingress-v1",
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "PORTAL_UNKNOWN"

    def test_unimplemented_api_uses_json_error_envelope(self) -> None:
        response = self.client.get(
            "/api/v2/not-implemented",
            HTTP_X_PORTAL="USER",
            HTTP_X_PROXY_CONTEXT="ingress-v1",
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    def test_openapi_exposes_health_and_sse_contracts(self) -> None:
        response = self.client.get(
            "/api/v2/schema",
            HTTP_X_PORTAL="USER",
            HTTP_X_PROXY_CONTEXT="ingress-v1",
        )

        assert response.status_code == 200
        document = yaml.safe_load(response.content)
        assert document["openapi"] == "3.0.3"
        assert "/api/v2/health" in document["paths"]
        assert "/api/v2/events/stream" in document["paths"]
        assert document["paths"]["/api/v2/events/stream"]["get"]["x-portals"] == [
            "USER",
            "TEACHING",
            "PLATFORM",
        ]
