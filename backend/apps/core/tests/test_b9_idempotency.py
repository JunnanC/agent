import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.test import RequestFactory

from apps.core.adapters.fake import (
    FAKE_DOWNLOAD_GRANT_REPOSITORY,
    FAKE_IDEMPOTENCY_REPOSITORY,
    FAKE_OBJECT_ASSET_REPOSITORY,
    IDEMPOTENCY_STORE_MAX_RECORDS,
    IdempotencyKeyConflict,
    IdempotencyStoreSaturated,
    IssuedDownloadGrant,
    StoredIdempotencySnapshot,
    issue_fake_download_grant,
)
from apps.core.testing.assertions import (
    capture_structured_logs,
    assert_error_envelope,
    assert_no_sensitive,
)
from apps.core.testing.cases import TraceTestCase
from apps.core.testing.tracing import portal_context, trace_context
from apps.core.views import DownloadGrantView


def issue(*, actor_user_id="42", key="key-b9", use="REPORT_DOWNLOAD", portal="USER"):
    return issue_fake_download_grant(
        actor_user_id=actor_user_id,
        portal=portal,
        asset_id="asset-001",
        use=use,
        idempotency_key=key,
    )


class DownloadGrantIdempotencyTests(TraceTestCase):
    def setUp(self):
        super().setUp()
        FAKE_OBJECT_ASSET_REPOSITORY.reset()
        FAKE_DOWNLOAD_GRANT_REPOSITORY.reset()
        FAKE_IDEMPOTENCY_REPOSITORY.reset()

    def post_download_grant(self, key):
        request = RequestFactory().post(
            "/api/v2/files/asset-001/download-grants",
            data={"use": "REPORT_DOWNLOAD"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        request.user = User(id=42, username="student-42")
        request.portal = "USER"
        csrf_token = get_token(request)
        request.COOKIES["csrftoken"] = csrf_token
        request.META["HTTP_X_CSRFTOKEN"] = csrf_token
        response = DownloadGrantView.as_view()(request, asset_id="asset-001")
        if hasattr(response, "render"):
            response.render()
        return response

    def test_same_actor_and_key_replays_exact_response(self):
        first = self.post_download_grant("key-b9-replay")
        second = self.post_download_grant("key-b9-replay")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(json.loads(first.content), json.loads(second.content))
        self.assertNotIn("X-Idempotent-Replay", first.headers)
        self.assertEqual(second.headers["X-Idempotent-Replay"], "true")
        self.assertEqual(second.headers["Cache-Control"], "private, no-store")
        self.assertEqual(len(FAKE_DOWNLOAD_GRANT_REPOSITORY.grants), 1)

    def test_same_key_is_isolated_by_actor(self):
        asset = FAKE_OBJECT_ASSET_REPOSITORY.assets["asset-001"]
        FAKE_OBJECT_ASSET_REPOSITORY.assets["asset-001"] = replace(
            asset,
            course_participant_user_ids=("42", "43"),
        )
        trace_id = "b" * 32

        with trace_context(trace_id=trace_id, portal="USER"):
            with portal_context("USER"):
                actor_a = issue(actor_user_id="42", key="shared-key")
                actor_b = issue(actor_user_id="43", key="shared-key")

        self.assertNotEqual(
            actor_a.grant.one_time_token,
            actor_b.grant.one_time_token,
        )
        self.assertFalse(actor_a.replayed)
        self.assertFalse(actor_b.replayed)
        self.assertEqual(len(FAKE_DOWNLOAD_GRANT_REPOSITORY.grants), 2)
        self.assertEqual(len(FAKE_IDEMPOTENCY_REPOSITORY.records), 2)

    def test_same_key_with_different_use_conflicts(self):
        with portal_context("USER"):
            issue(key="key-b9-use", use="REPORT_DOWNLOAD")

            with self.assertRaises(IdempotencyKeyConflict):
                issue(key="key-b9-use", use="ARCHIVE_EXPORT")

    def test_same_key_with_different_portal_conflicts(self):
        with portal_context("USER"):
            issue(key="key-b9-portal", portal="USER")

        with portal_context("TEACHING"):
            with self.assertRaises(IdempotencyKeyConflict):
                issue(key="key-b9-portal", portal="TEACHING")

    def test_concurrent_same_key_issues_one_grant(self):
        barrier = threading.Barrier(2)
        trace_id = "c" * 32

        def worker():
            barrier.wait()
            with trace_context(trace_id=trace_id, portal="USER"):
                with portal_context("USER"):
                    return issue(key="key-b9-concurrent")

        with capture_structured_logs() as captured:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(worker) for _ in range(2)]
                results = [future.result() for future in futures]

        records = captured.records()
        self.assertEqual(len(records), 2)
        self.assertTrue(all(record["trace_id"] == trace_id for record in records))
        assert_no_sensitive(json.dumps(records, ensure_ascii=False))

        self.assertEqual(
            results[0].grant.one_time_token,
            results[1].grant.one_time_token,
        )
        self.assertEqual(len(FAKE_DOWNLOAD_GRANT_REPOSITORY.grants), 1)
        self.assertEqual(len(FAKE_IDEMPOTENCY_REPOSITORY.records), 1)

    def test_plaintext_token_only_exists_in_idempotency_store(self):
        with portal_context("USER"):
            result = issue(key="key-b9-plaintext")

        grant_repository_text = repr(FAKE_DOWNLOAD_GRANT_REPOSITORY.grants)
        idempotency_repository_text = repr(FAKE_IDEMPOTENCY_REPOSITORY.records)
        self.assertNotIn(result.grant.one_time_token, grant_repository_text)
        self.assertIn(result.grant.one_time_token, idempotency_repository_text)
        assert_no_sensitive(grant_repository_text)

    def test_invalid_idempotency_keys_are_rejected(self):
        invalid_keys = ["", "k" * 256, "key-非ASCII"]

        for key in invalid_keys:
            with self.subTest(key=repr(key)):
                response = self.post_download_grant(key)
                assert_error_envelope(
                    json.loads(response.content),
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    json.loads(response.content)["code"],
                    "IDEMPOTENCY_KEY_INVALID",
                )

    def test_saturated_idempotency_store_rejects_new_keys(self):
        now = datetime.now(timezone.utc)
        for index in range(IDEMPOTENCY_STORE_MAX_RECORDS):
            FAKE_IDEMPOTENCY_REPOSITORY.records[
                ("42", f"key-saturated-{index}")
            ] = StoredIdempotencySnapshot(
                actor_user_id="42",
                idempotency_key=f"key-saturated-{index}",
                fingerprint="0" * 64,
                grant=IssuedDownloadGrant(
                    asset_id="asset-001",
                    one_time_token=f"snapshot-token-{index}",
                    expires_at=now + timedelta(seconds=120),
                    max_uses=1,
                ),
                expires_at=now + timedelta(seconds=120),
            )

        with portal_context("USER"):
            with self.assertRaises(IdempotencyStoreSaturated):
                issue(key="key-b9-new-after-saturation")

        self.assertEqual(
            len(FAKE_IDEMPOTENCY_REPOSITORY.records),
            IDEMPOTENCY_STORE_MAX_RECORDS,
        )
        self.assertEqual(len(FAKE_DOWNLOAD_GRANT_REPOSITORY.grants), 0)

    def test_expired_snapshot_is_swept_and_key_is_reissued(self):
        with portal_context("USER"):
            first = issue(key="key-b9-expired")

        stored_key = ("42", "key-b9-expired")
        FAKE_IDEMPOTENCY_REPOSITORY.records[stored_key] = replace(
            FAKE_IDEMPOTENCY_REPOSITORY.records[stored_key],
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )

        with portal_context("USER"):
            second = issue(key="key-b9-expired")

        self.assertNotEqual(
            first.grant.one_time_token,
            second.grant.one_time_token,
        )
        self.assertFalse(second.replayed)
        self.assertEqual(len(FAKE_DOWNLOAD_GRANT_REPOSITORY.grants), 2)
        self.assertEqual(len(FAKE_IDEMPOTENCY_REPOSITORY.records), 1)
