import json
import logging
from ipaddress import ip_network

from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from apps.core.adapters.fake import FAKE_DOWNLOAD_GRANT_REPOSITORY
from apps.core.testing import (
    TraceTestCase,
    assert_error_envelope,
    assert_no_object_storage_leak,
    assert_no_sensitive,
    capture_structured_logs,
    fake_traceparent,
    make_public_id,
    portal_context,
    trace_context,
)
from apps.core.tracing import bind_trace_context, current_portal, current_trace_id
from apps.core.views import DownloadGrantView


class TestingFactoryTests(TraceTestCase):
    def test_public_ids_are_opaque_and_unique(self):
        first = make_public_id("task")
        second = make_public_id("task")
        self.assertNotEqual(first, second)
        self.assertRegex(first, r"^task_[A-Za-z0-9_-]{32}$")
        self.assertFalse(first.removeprefix("task_").isdigit())

    def test_trace_context_restores_previous_trace(self):
        with trace_context(trace_id="0" * 31 + "1", portal="USER"):
            with trace_context(trace_id="0" * 31 + "2", portal="TEACHING"):
                self.assertEqual(current_trace_id(), "0" * 31 + "2")
            self.assertEqual(current_trace_id(), "0" * 31 + "1")
        self.assertIsNone(current_trace_id())

    def test_trace_test_case_clears_context_in_teardown(self):
        bind_trace_context(trace_id="0" * 31 + "4", portal="USER")
        self.tearDown()
        self.assertIsNone(current_trace_id())

    def test_fake_traceparent_matches_w3c_shape(self):
        trace_id = "0" * 31 + "2"
        traceparent = fake_traceparent(trace_id)
        self.assertEqual(
            traceparent,
            f"00-{trace_id}-{traceparent.split('-')[2]}-01",
        )
        self.assertRegex(
            traceparent,
            r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$",
        )
        self.assertIsNone(current_trace_id())

    def test_portal_context_restores_previous_portal(self):
        with portal_context("USER"):
            self.assertEqual(current_portal(), "USER")
        self.assertIsNone(current_portal())

    def test_error_envelope_accepts_exact_shape_and_requires_trace_id(self):
        assert_error_envelope(
            {
                "code": "NOT_FOUND",
                "message": "Resource not found",
                "details": {},
                "trace_id": "0" * 32,
            }
        )
        with self.assertRaises(AssertionError):
            assert_error_envelope(
                {
                    "code": "NOT_FOUND",
                    "message": "Resource not found",
                    "details": {},
                }
            )

    def test_structured_log_capture_parses_trace_and_portal(self):
        trace_id = "0" * 31 + "3"
        with trace_context(trace_id=trace_id, portal="USER"):
            with capture_structured_logs() as captured:
                logging.getLogger("apps.core.tests").info("operation completed")
        records = captured.records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["trace_id"], trace_id)
        self.assertEqual(records[0]["portal"], "USER")

    def test_sensitive_assertion_rejects_plaintext_token(self):
        with self.assertRaises(AssertionError):
            assert_no_sensitive("one_time_token=plaintext-token")


@override_settings(
    ALLOWED_HOSTS=["testserver", "user.localhost"],
    PORTAL_TRUSTED_PROXY_NETWORKS=[ip_network("127.0.0.0/8")],
    PORTAL_HOST_MAP={"USER": ["user.localhost"]},
)
class DownloadSecurityInvariantTests(TraceTestCase):
    def setUp(self):
        super().setUp()
        FAKE_DOWNLOAD_GRANT_REPOSITORY.reset()

    def tearDown(self):
        FAKE_DOWNLOAD_GRANT_REPOSITORY.reset()
        super().tearDown()

    def issue_grant(self):
        factory = APIRequestFactory(enforce_csrf_checks=True)
        request = factory.post(
            "/api/v2/files/asset-001/download-grants",
            data={"use": "REPORT_DOWNLOAD"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="key-b8-security",
        )
        request.user = User(id=42, username="student-42")
        request.portal = "USER"
        csrf_token = get_token(request)
        request.COOKIES["csrftoken"] = csrf_token
        request.META["HTTP_X_CSRFTOKEN"] = csrf_token
        response = DownloadGrantView.as_view()(request, asset_id="asset-001")
        response.render()
        return response

    def test_one_time_token_is_not_written_to_structured_logs(self):
        with capture_structured_logs() as captured:
            response = self.issue_grant()
            token = json.loads(response.content)["one_time_token"]
            logging.getLogger("apps.core.tests").info("download grant issued")
        log_text = "\n".join(json.dumps(record) for record in captured.records())
        self.assertNotIn(token, log_text)
        assert_no_sensitive(log_text)

    def test_download_response_does_not_leak_object_storage_topology(self):
        response = self.issue_grant()
        assert_no_object_storage_leak(response)
