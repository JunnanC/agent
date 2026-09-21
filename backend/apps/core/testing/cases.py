from django.test import SimpleTestCase

from apps.core.tracing import clear_trace_context


class TraceTestCase(SimpleTestCase):
    def setUp(self) -> None:
        super().setUp()
        clear_trace_context()

    def tearDown(self) -> None:
        clear_trace_context()
        super().tearDown()
