from __future__ import annotations

import unittest

from runtime.extend.contracts import RuntimeSpec
from runtime.extend.enums import InstanceStatus, RuntimeType
from runtime.extend.fake import FakeRuntimeAdapter


def make_spec() -> RuntimeSpec:
    return RuntimeSpec(
        runtime_type=RuntimeType.CONTAINER,
        image_digest="sha256:fake",
        cpu_limit=1,
        memory_limit_mib=512,
        disk_limit_mib=1024,
        process_limit=64,
        execution_timeout_seconds=600,
        allowed_access_modes=("WEB_IDE",),
    )


class RuntimeContractTests(unittest.TestCase):
    def test_fake_adapter_implements_nine_frozen_methods(self) -> None:
        expected = {
            "validate_spec", "create", "get_status", "get_progress",
            "issue_access", "snapshot", "stop", "destroy", "collect_metrics",
        }
        self.assertFalse(FakeRuntimeAdapter.__abstractmethods__)
        self.assertTrue(expected.issubset(set(dir(FakeRuntimeAdapter))))

    def test_instance_status_machine(self) -> None:
        self.assertTrue(InstanceStatus.REQUESTED.can_transition_to(InstanceStatus.PROVISIONING))
        self.assertFalse(InstanceStatus.REQUESTED.can_transition_to(InstanceStatus.RUNNING))
        self.assertFalse(InstanceStatus.DESTROYED.can_transition_to(InstanceStatus.FAILED))

    def test_spec_rejects_invalid_resources(self) -> None:
        with self.assertRaises(ValueError):
            RuntimeSpec(
                runtime_type=RuntimeType.CONTAINER,
                image_digest="sha256:fake",
                cpu_limit=0,
                memory_limit_mib=512,
                disk_limit_mib=512,
                process_limit=10,
                execution_timeout_seconds=60,
            )

    def test_spec_network_defaults_to_deny(self) -> None:
        self.assertFalse(make_spec().network_enabled)


if __name__ == "__main__":
    unittest.main()
