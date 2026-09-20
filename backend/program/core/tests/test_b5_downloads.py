import json

from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, APIClient

from core.adapters.fake import (
    FAKE_DOWNLOAD_GRANT_REPOSITORY,
    FAKE_OBJECT_ASSET_REPOSITORY,
)
from core.services import DownloadGrantService
from core.views import DownloadGrantView


@override_settings(ALLOWED_HOSTS=["testserver", "user.localhost"])
class B5ControlledDownloadTests(SimpleTestCase):
    def setUp(self):
        FAKE_OBJECT_ASSET_REPOSITORY.reset()
        FAKE_DOWNLOAD_GRANT_REPOSITORY.reset()
        self.user = User(id=42, username="student-42")

    def authorized_grant_request(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_authenticate(user=self.user)
        factory_request = RequestFactory().post(
            "/api/v2/files/asset-report-001/download-grants"
        )
        csrf_token = get_token(factory_request)
        client.cookies["csrftoken"] = csrf_token
        return client.post(
            "/api/v2/files/asset-report-001/download-grants",
            {"use": "REPORT_DOWNLOAD"},
            format="json",
            HTTP_HOST="user.localhost",
            HTTP_X_PORTAL="USER",
            HTTP_X_CSRFTOKEN=csrf_token,
            REMOTE_ADDR="127.0.0.1",
        )

    def issue_token(self):
        response = self.authorized_grant_request()
        self.assertEqual(response.status_code, 201)
        return response.json()["data"]["one_time_token"]

    def test_partition_a_without_csrf_is_rejected_with_error_envelope(self):
        factory = APIRequestFactory(enforce_csrf_checks=True)
        request = factory.post(
            "/api/v2/files/asset-report-001/download-grants",
            {"use": "REPORT_DOWNLOAD"},
            format="json",
            HTTP_HOST="user.localhost",
        )
        request.user = self.user
        response = DownloadGrantView.as_view()(
            request, asset_id="asset-report-001"
        )
        response.render()
        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(payload["error"]["code"], "CSRF_REQUIRED")
        self.assertTrue(payload["error"]["trace_id"])

    def test_partition_a_issues_hash_only_grant_with_session_and_csrf(self):
        response = self.authorized_grant_request()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        payload = response.json()["data"]
        self.assertTrue(payload["one_time_token"])
        stored = list(FAKE_DOWNLOAD_GRANT_REPOSITORY.grants.values())[0]
        self.assertNotIn(payload["one_time_token"], repr(stored))
        self.assertEqual(len(stored.token_hash), 64)

    def test_partition_b_does_not_require_session_or_csrf_and_is_501(self):
        token = self.issue_token()
        response = APIClient().get(
            f"/files/{token}",
            HTTP_HOST="user.localhost",
            HTTP_X_PORTAL="USER",
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        payload = response.json()["error"]
        self.assertEqual(payload["code"], "DOWNLOAD_STREAM_NOT_IMPLEMENTED")
        self.assertEqual(payload["details"]["slice"], "B5")

    def test_same_token_can_be_used_only_once(self):
        token = self.issue_token()
        client = APIClient()
        first = client.get(f"/files/{token}", HTTP_HOST="user.localhost")
        second = client.get(f"/files/{token}", HTTP_HOST="user.localhost")
        self.assertEqual(first.status_code, 501)
        self.assertEqual(second.status_code, 403)
        self.assertEqual(
            second.json()["error"]["details"]["reason"], "TOKEN_USES_EXHAUSTED"
        )

    def test_expired_token_is_rejected(self):
        grant = DownloadGrantService(token_ttl_seconds=-1).issue(
            actor_user_id="42",
            portal="USER",
            asset_id="asset-report-001",
            use="REPORT_DOWNLOAD",
        )
        response = APIClient().get(
            f"/files/{grant.one_time_token}", HTTP_HOST="user.localhost"
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"]["details"]["reason"], "TOKEN_EXPIRED"
        )

    def test_api_v2_file_token_variant_is_not_mounted(self):
        response = APIClient().get("/files/token-001", HTTP_HOST="user.localhost")
        self.assertEqual(response.status_code, 403)
        response = APIClient().get(
            "/api/v2/files/token-001", HTTP_HOST="user.localhost"
        )
        self.assertEqual(response.status_code, 404)

    def test_token_is_not_written_to_logs_or_response_addresses(self):
        with self.assertLogs("core.services", level="INFO") as captured:
            response = self.authorized_grant_request()
            token = response.json()["data"]["one_time_token"]
            APIClient().get(f"/files/{token}", HTTP_HOST="user.localhost")
        logs = "\n".join(captured.output)
        self.assertNotIn(token, logs)
        self.assertNotIn("minio", response.content.decode().lower())
        self.assertNotIn("bucket", response.content.decode().lower())
        self.assertNotIn("X-Accel-Redirect", response.headers)
