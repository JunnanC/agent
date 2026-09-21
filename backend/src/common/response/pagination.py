from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from common.response.success import get_trace_id


class StandardPagination(PageNumberPagination):
    """Return the page metadata required by the v2 list envelope."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "data": data,
                "meta": {
                    "page": self.page.number,
                    "page_size": self.get_page_size(self.request),
                    "total": self.page.paginator.count,
                    "trace_id": get_trace_id(self.request),
                },
            }
        )
