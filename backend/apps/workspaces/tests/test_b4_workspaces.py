import hashlib
import json
from ipaddress import ip_network

from django.test import SimpleTestCase, override_settings

from apps.core.testing import assert_error_envelope
from apps.workspaces.adapters import fake_workspace_token_adapter


@override_settings(
    ALLOWED_HOSTS=["testserver", "user.localhost"],
    PORTAL_TRUSTED_PROXY_NETWORKS=[ip_network("127.0.0.0/8")],
    PORTAL_HOST_MAP={"USER": ["user.localhost"]},
)
class B4WorkspaceTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        fake_workspace_token_adapter.reset()

    def request(self, method, path, **kwargs):
        extra = {
            "HTTP_HOST": "user.localhost",
            "HTTP_X_PORTAL": "USER",
            "REMOTE_ADDR": "127.0.0.1",
        }
        extra.update(kwargs.pop("extra", {}))
        return getattr(self.client, method)(path, **kwargs, **extra)

    def issue(self, idempotency_key="018f2d5e-b1f2-7000-8000-000000000001"):
        return self.request(
            "post",
            "/api/v2/tasks/task-001/workspace-sessions",
            data={
                "student_public_id": "student-001",
                "instance_public_id": "instance-001",
            },
            content_type="application/json",
            extra={"HTTP_IDEMPOTENCY_KEY": idempotency_key},
        )

    def test_issue_requires_idempotency_key(self):
        response = self.request(
            "post",
            "/api/v2/tasks/task-001/workspace-sessions",
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(payload["code"], "IDEMPOTENCY_KEY_REQUIRED")
        assert_error_envelope(payload)

    def test_issue_is_idempotent_and_returns_token_once(self):
        first = self.issue()
        second = self.issue()
        first_payload = first.json()
        second_payload = second.json()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertTrue(first_payload["token"])
        self.assertEqual(second_payload["token"], "")
        self.assertTrue(second_payload["replayed"])
        self.assertEqual(
            first_payload["session_public_id"],
            second_payload["session_public_id"],
        )
        self.assertEqual(first["Cache-Control"], "private, no-store")

    def test_snapshot_is_monotonic_and_idempotent(self):
        path = "/api/v2/tasks/task-001/workspace-snapshot"
        newer = self.request(
            "put",
            path,
            data={"client_seq": 3, "payload": {"cursor": 3}},
            content_type="application/json",
        )
        older = self.request(
            "put",
            path,
            data={"client_seq": 2, "payload": {"cursor": 2}},
            content_type="application/json",
        )
        repeated = self.request(
            "put",
            path,
            data={"client_seq": 3, "payload": {"cursor": 3}},
            content_type="application/json",
        )
        self.assertEqual(newer.status_code, 200)
        self.assertEqual(older.status_code, 409)
        self.assertEqual(older.json()["code"], "CLIENT_SEQ_CONFLICT")
        self.assertEqual(repeated.status_code, 200)
        self.assertTrue(repeated.json()["idempotent_replay"])

    def test_renew_revoke_and_internal_verify(self):
        issued = self.issue().json()
        renewed = self.request(
            "post",
            f"/api/v2/workspace-sessions/{issued['session_public_id']}/renew",
            data={
                "task_public_id": "task-001",
                "student_public_id": "student-001",
                "instance_public_id": "instance-001",
            },
            content_type="application/json",
        )
        self.assertEqual(renewed.status_code, 200)

        token_hash = hashlib.sha256(renewed.json()["token"].encode()).hexdigest()
        verified = self.client.post(
            "/internal/workspace-tokens/verify",
            data={
                "token_hash": token_hash,
                "task_public_id": "task-001",
                "student_public_id": "student-001",
                "instance_public_id": "instance-001",
            },
            content_type="application/json",
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(verified.json()["valid"])

        revoked = self.request(
            "post",
            f"/api/v2/workspace-sessions/{issued['session_public_id']}/revoke",
            data={"student_public_id": "student-001"},
            content_type="application/json",
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertTrue(revoked.json()["revoked"])
        self.assertTrue(fake_workspace_token_adapter.audit_facts())

    def test_internal_verify_from_untrusted_source_is_404(self):
        response = self.client.post(
            "/internal/workspace-tokens/verify",
            data={},
            content_type="application/json",
            REMOTE_ADDR="203.0.113.10",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "NOT_FOUND")
