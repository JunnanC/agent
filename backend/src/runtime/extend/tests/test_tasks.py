from __future__ import annotations

import unittest

from runtime.extend.enums import CompensationFailureStage, CompensationStatus
from runtime.extend.tasks import InlineTaskBroker, RetryPolicy, WorkerTaskRequest


class CeleryPolicyTests(unittest.TestCase):
    def test_exponential_backoff_is_bounded(self) -> None:
        policy = RetryPolicy()
        self.assertEqual(policy.delay_for_attempt(1), 2)
        self.assertEqual(policy.delay_for_attempt(2), 4)
        self.assertEqual(policy.delay_for_attempt(10), 300)

    def test_attempts_exceeding_limit_go_manual(self) -> None:
        policy = RetryPolicy()
        self.assertFalse(policy.requires_manual_handling(4))
        self.assertTrue(policy.requires_manual_handling(5))

    def test_inline_broker_records_worker_request(self) -> None:
        received: list[WorkerTaskRequest] = []
        broker = InlineTaskBroker(received.append)
        broker.send_task("runtime.provision", {"operation_id": "op", "trace_id": "trace"})
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].task_name, "runtime.provision")

    def test_compensation_status_mapping(self) -> None:
        self.assertEqual(
            CompensationFailureStage.PROVISIONING,
            CompensationFailureStage("PROVISIONING"),
        )
        self.assertEqual(CompensationStatus.MANUAL, CompensationStatus("MANUAL"))


if __name__ == "__main__":
    unittest.main()
