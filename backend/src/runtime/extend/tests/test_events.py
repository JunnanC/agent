from __future__ import annotations

import json
import unittest
from uuid import uuid4

from runtime.extend.events import SSEEvent, SSEEventType, SSEStage


class SSEEventTests(unittest.TestCase):
    def test_payload_has_exactly_twelve_fields(self) -> None:
        event = SSEEvent.create(
            event_type=SSEEventType.PROVISIONING_STEP_UPDATED,
            assignment_id=1,
            instance_id=2,
            operation_id=str(uuid4()),
            status="RUNNING",
            message="正在拉取镜像",
            trace_id=str(uuid4()),
            stage=SSEStage.IMAGE_PULL,
            progress_percent=30,
        )
        self.assertEqual(
            set(event.payload()),
            {
                "event_id", "event_type", "occurred_at", "assignment_id",
                "instance_id", "operation_id", "stage", "status",
                "progress_percent", "message", "retryable", "trace_id",
            },
        )
        self.assertTrue(event.occurred_at.endswith("+00:00"))

    def test_wire_format_is_sse_compatible(self) -> None:
        event = SSEEvent.create(
            event_type=SSEEventType.INSTANCE_STATE_CHANGED,
            assignment_id=1,
            instance_id=2,
            operation_id=str(uuid4()),
            status="READY",
            message="实例已就绪",
            trace_id=str(uuid4()),
            progress_percent=100,
        )
        wire = event.to_wire()
        event_line, id_line, data_line = wire.splitlines()[:3]
        self.assertEqual(event_line, "event:INSTANCE_STATE_CHANGED")
        self.assertTrue(id_line.startswith("id:"))
        self.assertTrue(data_line.startswith("data:"))
        self.assertEqual(json.loads(data_line.removeprefix("data:"))["event_id"], event.event_id)
        self.assertTrue(wire.endswith("\n\n"))

    def test_rejects_invalid_progress(self) -> None:
        with self.assertRaises(ValueError):
            SSEEvent.create(
                event_type=SSEEventType.PROVISIONING_COMPLETED,
                assignment_id=1,
                instance_id=2,
                operation_id=str(uuid4()),
                status="SUCCEEDED",
                message="完成",
                trace_id=str(uuid4()),
                progress_percent=101,
            )


if __name__ == "__main__":
    unittest.main()
