from __future__ import annotations

import unittest

from apps.runtime.contracts import RuntimeSpec
from apps.runtime.enums import InstanceStatus, RuntimeType
from apps.runtime.fake import FakeRuntimeAdapter


def make_spec() -> RuntimeSpec:
    return RuntimeSpec(
        runtime_type=RuntimeType.CONTAINER,
        image_digest="sha256:fake",
        cpu_limit=1,
        memory_limit_mib=512,
        disk_limit_mib=1024,
        process_limit=64,
        execution_timeout_seconds=600,
    )


class FakeRuntimeAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = FakeRuntimeAdapter()

    def test_validate_and_create_are_idempotent(self) -> None:
        spec = make_spec()
        validated = self.adapter.validate_spec(spec, idempotency_key="key-1")
        self.assertTrue(validated.ok)
        first = self.adapter.create(spec, idempotency_key="key-1")
        second = self.adapter.create(spec, idempotency_key="key-1")
        self.assertTrue(first.ok)
        self.assertFalse(first.data["idempotent_replay"])
        self.assertTrue(second.data["idempotent_replay"])
        self.assertEqual(first.data["runtime_instance_id"], second.data["runtime_instance_id"])

    def test_missing_idempotency_key_is_rejected(self) -> None:
        self.assertFalse(self.adapter.validate_spec(make_spec(), idempotency_key="").ok)
        self.assertFalse(self.adapter.create(make_spec(), idempotency_key="").ok)
        self.assertFalse(self.adapter.destroy("missing", idempotency_key="").ok)

    def test_issue_access_stop_snapshot_destroy_and_metrics(self) -> None:
        created = self.adapter.create(make_spec(), idempotency_key="key-2")
        runtime_id = created.data["runtime_instance_id"]
        self.assertEqual(self.adapter.get_status(runtime_id).status, InstanceStatus.PROVISIONING)
        self.assertFalse(self.adapter.issue_access(runtime_id, "user-1", "WEB_IDE").ok)

        self.adapter._runtimes[runtime_id]["status"] = InstanceStatus.READY
        access = self.adapter.issue_access(runtime_id, "user-1", "WEB_IDE")
        self.assertTrue(access.ok)
        self.assertIn("fake-token-", access.data["access"].short_term_token)

        self.assertTrue(self.adapter.snapshot(runtime_id, {"retention": "ARCHIVE"}).ok)
        self.assertTrue(self.adapter.stop(runtime_id).ok)
        self.assertIsInstance(self.adapter.collect_metrics(runtime_id).process_count, int)

        first = self.adapter.destroy(runtime_id, idempotency_key="destroy-1")
        second = self.adapter.destroy(runtime_id, idempotency_key="destroy-1")
        self.assertTrue(first.ok)
        self.assertTrue(second.ok)
        self.assertFalse(first.data["idempotent_replay"])
        self.assertTrue(second.data["idempotent_replay"])

    def test_unknown_runtime_returns_stable_error(self) -> None:
        result = self.adapter.get_status("missing")
        self.assertEqual(result.status, InstanceStatus.FAILED)
        self.assertEqual(result.error.error_code, "RUNTIME_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
