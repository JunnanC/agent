import json
import logging
import re
from ipaddress import ip_network
from unittest.mock import patch

from django.http import HttpResponse
from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.core.views import DownloadGrantView

from education_experiment_platform.celery import (
    bind_worker_trace_context,
    clear_worker_trace_context,
    propagate_trace_headers,
)
from apps.core.logging import StructuredJsonFormatter, SensitiveDataFilter
from apps.core.middleware import PortalContextMiddleware
from apps.core.schema import add_trace_response_header
from apps.core.tracing import (
    bind_celery_queue,
    bind_trace_context,
    clear_trace_context,
    current_portal,
    current_trace_id,
    new_trace_id,
    trace_headers,
)


TRACE_ID = "0123456789abcdef0123456789abcdef"
TRACEPARENT = f"00-{TRACE_ID}-0123456789abcdef-01"


def clear_context():
    clear_trace_context()


class TracingTests(SimpleTestCase):
    def setUp(self):
        clear_context()

    def tearDown(self):
        clear_context()

    def test_trace_context_binds_and_clears(self):
        bind_trace_context(trace_id=TRACE_ID, portal="USER")
        self.assertEqual(current_trace_id(), TRACE_ID)
        self.assertEqual(current_portal(), "USER")
        clear_trace_context()
        self.assertIsNone(current_trace_id())
        self.assertIsNone(current_portal())

    def test_generated_trace_id_uses_w3c_shape(self):
        self.assertRegex(new_trace_id(), r"^[0-9a-f]{32}$")

    def test_trace_headers_use_current_trace_id(self):
        bind_trace_context(trace_id=TRACE_ID)
        header = trace_headers()["traceparent"]
        self.assertTrue(re.fullmatch(
            rf"00-{TRACE_ID}-[0-9a-f]{{16}}-01",
            header,
        ))


@override_settings(
    ALLOWED_HOSTS=["testserver", "user.localhost"],
    PORTAL_TRUSTED_PROXY_NETWORKS=[ip_network("127.0.0.0/8")],
    PORTAL_HOST_MAP={"USER": ["user.localhost"]},
)
class MiddlewareTraceTests(SimpleTestCase):
    def setUp(self):
        clear_context()
        self.factory = RequestFactory()

    def tearDown(self):
        clear_context()

    def request(self, path="/health", traceparent=None, extra=None):
        headers = {"HTTP_HOST": "user.localhost"}
        if traceparent:
            headers["HTTP_TRACEPARENT"] = traceparent
        if extra:
            headers.update(extra)
        request = self.factory.get(path, **headers)
        request.REMOTE_ADDR = "127.0.0.1"
        return request

    def test_health_inherits_trace_id_and_sets_response_header(self):
        response = PortalContextMiddleware(lambda request: HttpResponse())(
            self.request(traceparent=TRACEPARENT)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Trace-Id"], TRACE_ID)
        self.assertEqual(current_trace_id(), TRACE_ID)
        response.close()
        self.assertIsNone(current_trace_id())

    def test_generated_trace_id_has_w3c_shape(self):
        response = PortalContextMiddleware(lambda request: HttpResponse())(
            self.request()
        )
        self.assertRegex(response["X-Trace-Id"], r"^[0-9a-f]{32}$")

    def test_portal_context_is_available_during_request(self):
        seen = {}

        def view(request):
            seen["trace_id"] = current_trace_id()
            seen["portal"] = current_portal()
            return HttpResponse()

        PortalContextMiddleware(view)(
            self.request(
                path="/api/v2/events/stream",
                traceparent=TRACEPARENT,
                extra={"HTTP_X_PORTAL": "USER"},
            )
        )
        self.assertEqual(seen, {"trace_id": TRACE_ID, "portal": "USER"})

    def test_all_portal_values_are_available_during_request(self):
        for portal in ("USER", "TEACHING", "PLATFORM"):
            with self.settings(
                ALLOWED_HOSTS=["testserver", f"{portal.lower()}.localhost"],
                PORTAL_HOST_MAP={portal: [f"{portal.lower()}.localhost"]},
            ):
                request = self.factory.get(
                    "/api/v2/events/stream",
                    HTTP_HOST=f"{portal.lower()}.localhost",
                    HTTP_X_PORTAL=portal,
                    HTTP_TRACEPARENT=TRACEPARENT,
                )
                request.REMOTE_ADDR = "127.0.0.1"
                seen = {}

                def view(request):
                    seen["portal"] = current_portal()
                    return HttpResponse()

                PortalContextMiddleware(view)(request)
                self.assertEqual(seen, {"portal": portal})

    def test_error_endpoint_response_header_matches_envelope(self):
        response = self.client.get(
            "/files/token-001",
            HTTP_HOST="user.localhost",
            HTTP_X_PORTAL="USER",
            REMOTE_ADDR="127.0.0.1",
            HTTP_TRACEPARENT=TRACEPARENT,
        )
        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 501)
        self.assertEqual(response["X-Trace-Id"], payload["trace_id"])
        self.assertEqual(response["X-Trace-Id"], TRACE_ID)

    def test_download_grant_success_response_has_trace_header(self):
        factory = APIRequestFactory(enforce_csrf_checks=True)
        request = factory.post(
            "/api/v2/files/asset-001/download-grants",
            data={"use": "REPORT_DOWNLOAD"},
            content_type="application/json",
            HTTP_HOST="user.localhost",
            HTTP_X_PORTAL="USER",
            REMOTE_ADDR="127.0.0.1",
            HTTP_IDEMPOTENCY_KEY="key-b7-trace",
            HTTP_TRACEPARENT=TRACEPARENT,
        )
        request.user = User(id=42, username="student-42")
        request.portal = "USER"
        csrf_token = get_token(request)
        request.COOKIES["csrftoken"] = csrf_token
        request.META["HTTP_X_CSRFTOKEN"] = csrf_token

        def view(request):
            return DownloadGrantView.as_view()(request, asset_id="asset-001")

        response = PortalContextMiddleware(view)(request)
        response.render()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response["X-Trace-Id"], TRACE_ID)


class StructuredLoggingTests(SimpleTestCase):
    def setUp(self):
        clear_context()

    def tearDown(self):
        clear_context()

    def record(self, **extra):
        record = logging.LogRecord(
            name="apps.core.tests",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="operation completed",
            args=(),
            exc_info=None,
        )
        for key, value in extra.items():
            setattr(record, key, value)
        return record

    def test_formatter_outputs_required_json_fields(self):
        bind_trace_context(trace_id=TRACE_ID, portal="USER")
        bind_celery_queue("q_default")
        output = StructuredJsonFormatter().format(
            self.record(action="issue-grant", result="success", duration_ms=12)
        )
        payload = json.loads(output)
        self.assertEqual(
            set(payload) & {
                "timestamp", "level", "service", "portal", "trace_id",
                "celery_queue", "action", "result", "duration_ms",
            },
            {
                "timestamp", "level", "service", "portal", "trace_id",
                "celery_queue", "action", "result", "duration_ms",
            },
        )
        self.assertEqual(payload["service"], "django")
        self.assertEqual(payload["portal"], "USER")
        self.assertEqual(payload["trace_id"], TRACE_ID)
        self.assertEqual(payload["duration_ms"], 12)

    def test_sensitive_values_are_redacted(self):
        record = self.record()
        record.msg = (
            "password=secret-password csrf_token=csrf-secret "
            "prompt=full prompt value "
            "url=https://example.com/file?X-Amz-Signature=signed-secret"
        )
        SensitiveDataFilter().filter(record)
        output = StructuredJsonFormatter().format(record)
        self.assertNotIn("secret-password", output)
        self.assertNotIn("csrf-secret", output)
        self.assertNotIn("full prompt value", output)
        self.assertNotIn("signed-secret", output)
        self.assertIn("***REDACTED***", output)

    def test_formatter_failure_degrades_to_plain_text(self):
        with patch(
            "apps.core.logging.json.dumps",
            side_effect=RuntimeError("formatter failed"),
        ):
            output = StructuredJsonFormatter().format(self.record())
        self.assertIsInstance(output, str)
        self.assertEqual(len(output.splitlines()), 1)
        self.assertIn("operation completed", output)


class FakeTask:
    def __init__(self, headers):
        self.request = type(
            "Request",
            (),
            {
                "headers": headers,
                "delivery_info": {"routing_key": "q_default"},
            },
        )()


class CeleryTraceTests(SimpleTestCase):
    def setUp(self):
        clear_context()

    def tearDown(self):
        clear_context()

    def test_publish_and_worker_use_same_trace_id(self):
        bind_trace_context(trace_id=TRACE_ID)
        headers = {}
        propagate_trace_headers(headers=headers)
        bind_worker_trace_context(task=FakeTask(headers))
        self.assertEqual(current_trace_id(), TRACE_ID)
        clear_worker_trace_context()
        self.assertIsNone(current_trace_id())

    def test_worker_generates_trace_when_header_is_missing(self):
        bind_worker_trace_context(task=FakeTask({}))
        self.assertRegex(current_trace_id(), r"^[0-9a-f]{32}$")
        clear_worker_trace_context()


class SchemaTraceHeaderTests(SimpleTestCase):
    def test_postprocessing_hook_adds_trace_response_header(self):
        result = add_trace_response_header(
            {"paths": {"/health": {"get": {"responses": {"200": {}}}}}}
        )
        response = result["paths"]["/health"]["get"]["responses"]["200"]
        self.assertEqual(
            response["headers"]["X-Trace-Id"]["schema"],
            {"type": "string"},
        )
