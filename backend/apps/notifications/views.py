from __future__ import annotations

import time
from itertools import chain
from typing import Iterator

from django.http import StreamingHttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.core.http import error_response
from apps.notifications.adapters import InMemoryEventSource, MemoryEventDeduplicator
from apps.notifications.events import (
    DomainEvent,
    encode_sse_frame,
    event_allowed_for_portal,
    heartbeat_frame,
    resync_required_frame,
)


@extend_schema(
    request=None,
    tags=["notifications"],
    responses={
        200: OpenApiResponse(
            response=None,
            description=(
                "Non-JSON text/event-stream response. Generated clients must "
                "exclude this operation and use the frontend event-client."
            ),
        )
    },
)
class EventStreamView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    event_source = InMemoryEventSource()
    heartbeat_interval = 15.0

    def get(self, request):
        portal = getattr(request, "portal", None)
        if portal is None:
            return error_response(
                status_code=400,
                code="PORTAL_CONTEXT_INVALID",
                message="请求上下文无效",
                details={},
                request=request,
            )

        last_event_id = request.headers.get("Last-Event-ID")
        if last_event_id is not None and not self.event_source.has_event(last_event_id):
            return self._sse_response(self._resync_generator(last_event_id))

        events = self.event_source.stream(portal, last_event_id)
        try:
            first_event = next(events)
        except StopIteration:
            return self._sse_response(self._heartbeat_only_generator())

        if not event_allowed_for_portal(first_event, portal):
            return error_response(
                status_code=403,
                code="EVENT_SCOPE_FORBIDDEN",
                message="当前 portal 无权订阅该事件",
                details={"portal": portal},
                request=request,
            )

        return self._sse_response(self._event_generator(first_event, events, portal))

    def _sse_response(self, frames: Iterator[str]) -> StreamingHttpResponse:
        response = StreamingHttpResponse(frames, content_type="text/event-stream")
        response.headers["Cache-Control"] = "no-cache, no-transform"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    def _event_generator(
        self,
        first_event: DomainEvent,
        events: Iterator[DomainEvent],
        portal: str,
    ) -> Iterator[str]:
        deduplicator = MemoryEventDeduplicator()
        for event in chain([first_event], events):
            if not event_allowed_for_portal(event, portal):
                continue
            if deduplicator.seen(event.event_id):
                continue
            deduplicator.mark_seen(event.event_id)
            yield encode_sse_frame(event)
        yield from self._heartbeat_only_generator()

    def _heartbeat_only_generator(self) -> Iterator[str]:
        while True:
            yield heartbeat_frame()
            time.sleep(self.heartbeat_interval)

    def _resync_generator(self, last_event_id: str) -> Iterator[str]:
        yield resync_required_frame(last_event_id)
        yield from self._heartbeat_only_generator()
