from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.http import idempotency_key_required, not_implemented


@extend_schema(request=None, tags=["core"], responses=None)
class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "ok", "trace_id": request.trace_id})


@extend_schema(
    request=None,
    tags=["core"],
    responses={
        200: OpenApiResponse(
            response=None,
            description=(
                "Non-JSON file stream response. Generated clients must "
                "exclude this operation and use the returned download URL."
            ),
        )
    },
)
class FileDownloadPlaceholderView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, one_time_token):
        return not_implemented(
            request,
            "B5",
            f"/files/{one_time_token}",
        )


@extend_schema(request=None, tags=["core"], responses=None)
class DownloadGrantPlaceholderView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def dispatch(self, request, *args, **kwargs):
        if not request.headers.get("Idempotency-Key"):
            return idempotency_key_required(
                request,
                "/api/v2/files/{asset_id}/download-grants".format(**kwargs),
            )
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, asset_id):
        return not_implemented(
            request,
            "B5",
            f"/api/v2/files/{asset_id}/download-grants",
        )
