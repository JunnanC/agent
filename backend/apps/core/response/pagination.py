from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from ..context import current_request_id, current_trace_id


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        request_id = self.request.headers.get("X-Request-ID", current_request_id())
        trace_id = self.request.headers.get("X-Trace-ID", current_trace_id())
        return Response(
            {
                "data": {
                    "items": data,
                    "page": self.page.number,
                    "page_size": self.get_page_size(self.request),
                    "total": self.page.paginator.count,
                },
                "meta": {
                    "message": "ok",
                    "request_id": request_id,
                    "trace_id": trace_id,
                },
                "error": None,
            }
        )
