from collections.abc import Iterator

from django.http import StreamingHttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView


def _probe_event(trace_id: str) -> Iterator[bytes]:
    yield f": stream-ready trace_id={trace_id}\n\n".encode()


class EventStreamView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        tags=["events"],
        summary="Portal event stream",
        responses={
            (200, "text/event-stream"): OpenApiResponse(description="Server-sent event stream")
        },
        extensions={"x-portals": ["USER", "TEACHING", "PLATFORM"]},
    )
    def get(self, request: Request) -> StreamingHttpResponse:
        response = StreamingHttpResponse(
            _probe_event(getattr(request, "trace_id", "")), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache, no-store"
        response["X-Accel-Buffering"] = "no"
        return response
