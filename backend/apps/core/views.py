from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.adapters.fake import (
    FAKE_DOWNLOAD_GRANT_REPOSITORY,
    issue_fake_download_grant,
)
from apps.core.http import error_response, idempotency_key_required, not_implemented
from apps.core.serializers import (
    DownloadGrantRequestSerializer,
    DownloadGrantResponseSerializer,
)


@extend_schema(exclude=True)
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


@extend_schema(
    tags=["core"],
    request=DownloadGrantRequestSerializer,
    responses={201: DownloadGrantResponseSerializer},
)
class DownloadGrantView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication]

    def dispatch(self, request, *args, **kwargs):
        if not request.headers.get("Idempotency-Key"):
            return idempotency_key_required(
                request,
            "/api/v2/files/{asset_id}/download-grants".format(**kwargs),
        )
        return super().dispatch(request, *args, **kwargs)

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        if response.status_code == 403 and str(detail).startswith("CSRF Failed"):
            return error_response(
                status_code=403,
                code="CSRF_REQUIRED",
                message="缺少或无效的 CSRF token",
                details={},
                request=self.request,
            )
        return response

    def post(self, request, asset_id):
        serializer = DownloadGrantRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            grant = issue_fake_download_grant(
                actor_user_id=str(request.user.pk),
                portal=request.portal,
                asset_id=asset_id,
                use=serializer.validated_data["use"],
            )
        except ValueError as error:
            return error_response(
                status_code=404,
                code="RESOURCE_NOT_FOUND",
                message="资源不存在",
                details={"reason": str(error)},
                request=request,
            )
        except PermissionError as error:
            return error_response(
                status_code=403,
                code="DOWNLOAD_GRANT_DENIED",
                message="不允许下载该对象",
                details={"reason": str(error)},
                request=request,
            )

        response = Response(
            {
                "asset_id": grant.asset_id,
                "one_time_token": grant.one_time_token,
                "expires_at": grant.expires_at.isoformat(),
                "max_uses": grant.max_uses,
            },
            status=201,
        )
        response["Cache-Control"] = "private, no-store"
        return response
