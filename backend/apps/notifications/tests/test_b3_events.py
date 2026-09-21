import json
from ipaddress import ip_network

from django.test import SimpleTestCase, override_settings

from apps.core.testing import assert_event_envelope
from apps.notifications.adapters import InMemoryEventSource
from apps.notifications.events import (
    EVENT_PLATFORM_ALERT,
    EVENT_TASK_STATUS_CHANGED,
    build_event,
)
from apps.notifications.views import EventStreamView


@override_settings(
    ALLOWED_HOSTS=["testserver", "user.localhost"],
    PORTAL_TRUSTED_PROXY_NETWORKS=[ip_network("127.0.0.0/8")],
    PORTAL_HOST_MAP={"USER": ["user.localhost"]},
)
class EventStreamTests(SimpleTestCase):
    def setUp(self):
        self.original_source = EventStreamView.event_source
        EventStreamView.event_source = InMemoryEventSource()

    def tearDown(self):
        EventStreamView.event_source = self.original_source

    def request(self, **extra):
        headers = {
            "HTTP_HOST": "user.localhost",
            "HTTP_X_PORTAL": "USER",
            "REMOTE_ADDR": "127.0.0.1",
        }
        headers.update(extra)
        return self.client.get("/api/v2/events/stream", **headers)

    def inject_task_event(self, *, data=None, **extra):
        event = build_event(
            event_id="1726639200000-2",
            event_type=EVENT_TASK_STATUS_CHANGED,
            course_id="course-001",
            subject_id="task-001",
            occurred_at="2026-09-18T14:00:00+08:00",
            data=data if data is not None else {"status": "completed"},
            trace_id="trace-001",
            **extra,
        )
        EventStreamView.event_source.inject(event)
        return event

    def test_response_headers(self):
        response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "text/event-stream")
        self.assertEqual(response.headers["Cache-Control"], "no-cache, no-transform")
        self.assertEqual(response.headers["X-Accel-Buffering"], "no")

    def test_missing_portal_context_returns_400(self):
        response = self.client.get("/api/v2/events/stream")
        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertEqual(payload["code"], "PORTAL_CONTEXT_INVALID")
        self.assertTrue(payload["trace_id"])

    def test_scope_mismatch_returns_403(self):
        EventStreamView.event_source.inject(
            build_event(
                event_id="1726639200000-3",
                event_type=EVENT_PLATFORM_ALERT,
                occurred_at="2026-09-18T14:00:00+08:00",
                data={"severity": "warning"},
                trace_id="trace-002",
            )
        )
        response = self.request()
        self.assertEqual(response.status_code, 403)
        payload = json.loads(response.content)
        self.assertEqual(payload["code"], "EVENT_SCOPE_FORBIDDEN")
        self.assertTrue(payload["trace_id"])

    def test_heartbeat_does_not_write_business_state(self):
        response = self.request()
        frame = next(response.streaming_content)
        self.assertEqual(frame, b": heartbeat\n\n")

    def test_task_event_uses_d007_frame(self):
        self.inject_task_event()
        response = self.request()
        frame = next(response.streaming_content).decode()
        lines = frame.splitlines()
        self.assertEqual(lines[0], "id: 1726639200000-2")
        self.assertEqual(lines[1], "event: task.status_changed")
        self.assertTrue(lines[2].startswith("data: "))
        payload = json.loads(lines[2][len("data: ") :])
        assert_event_envelope(payload)
        self.assertNotIn("id", payload)
        self.assertNotIn("type", payload)

    def test_sensitive_fields_are_filtered_and_logged_without_values(self):
        with self.assertLogs("apps.notifications.events", level="WARNING") as captured:
            self.inject_task_event(
                workspace_token="secret-token",
                data={
                    "status": "completed",
                    "workspace_token": "secret-token",
                    "nested": {"signed_url": "https://example.com/signed"},
                },
            )
        response = self.request()
        frame = next(response.streaming_content).decode()
        self.assertNotIn("secret-token", frame)
        self.assertNotIn("https://example.com/signed", frame)
        payload = json.loads(frame.splitlines()[2][len("data: ") :])
        self.assertEqual(payload["data"], {"status": "completed", "nested": {}})
        self.assertTrue(
            any("workspace_token" in message and "secret-token" not in message for message in captured.output)
        )

    def test_last_event_id_replays_only_newer_events(self):
        first = self.inject_task_event()
        EventStreamView.event_source.inject(
            build_event(
                event_id="1726639200000-4",
                event_type=EVENT_TASK_STATUS_CHANGED,
                course_id="course-001",
                subject_id="task-002",
                occurred_at="2026-09-18T14:01:00+08:00",
                data={"status": "running"},
                trace_id="trace-003",
            )
        )
        response = self.request(HTTP_LAST_EVENT_ID=first.event_id)
        frame = next(response.streaming_content).decode()
        self.assertIn("id: 1726639200000-4", frame)
        self.assertNotIn("id: 1726639200000-2", frame)

    def test_unknown_last_event_id_requests_resync(self):
        self.inject_task_event()
        response = self.request(HTTP_LAST_EVENT_ID="missing")
        frame = next(response.streaming_content).decode()
        self.assertIn("event: resync.required", frame)
