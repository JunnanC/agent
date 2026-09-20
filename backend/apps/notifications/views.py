from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.core.http import not_implemented


@extend_schema(request=None, responses=None)
class EventStreamView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return not_implemented(request, "B3", "/api/v2/events/stream")
