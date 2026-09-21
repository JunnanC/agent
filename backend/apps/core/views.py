from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.adapters.fake import (
    IDEMPOTENCY_KEY_PATTERN,
    FAKE_DOWNLOAD_GRANT_REPOSITORY,
    IdempotencyKeyConflict,
    IdempotencyKeyInvalid,
    IdempotencyStoreSaturated,
    issue_fake_download_grant,
)
from apps.core.http import (
    error_response,
    idempotency_key_invalid,
    idempotency_key_required,
    not_implemented,
)
from apps.core.serializers import (
    DownloadGrantRequestSerializer,
    DownloadGrantResponseSerializer,
    ErrorEnvelopeSerializer,
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
    parameters=[
        OpenApiParameter(
            name="Idempotency-Key",
            location=OpenApiParameter.HEADER,
            required=True,
            type=OpenApiTypes.STR,
            description="Client-generated idempotency key for the write operation.",
        ),
        OpenApiParameter(
            name="X-Idempotent-Replay",
            location=OpenApiParameter.HEADER,
            type=OpenApiTypes.STR,
            response=[201],
            description="Set to true when the response replays the original grant.",
        ),
    ],
    responses={
        201: OpenApiResponse(
            response=DownloadGrantResponseSerializer,
            description="Grant issued or replayed.",
        ),
        400: OpenApiResponse(
            response=ErrorEnvelopeSerializer,
            description="Idempotency-Key is missing or invalid, or request validation failed.",
        ),
        403: OpenApiResponse(
            response=ErrorEnvelopeSerializer,
            description="CSRF is required or the actor is not allowed to download the object.",
        ),
        404: OpenApiResponse(
            response=ErrorEnvelopeSerializer,
            description="Object asset does not exist.",
        ),
        409: OpenApiResponse(
            response=ErrorEnvelopeSerializer,
            description="The Idempotency-Key was already used with a different request fingerprint.",
        ),
        429: OpenApiResponse(
            response=ErrorEnvelopeSerializer,
            description="The in-memory idempotency store is saturated.",
        ),
    },
)
class DownloadGrantView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication]

    def dispatch(self, request, *args, **kwargs):
        idempotency_key = request.headers.get("Idempotency-Key")
        route = "/api/v2/files/{asset_id}/download-grants".format(**kwargs)
        if idempotency_key is None:
            return idempotency_key_required(
                request,
                route,
            )
        if IDEMPOTENCY_KEY_PATTERN.fullmatch(idempotency_key) is None:
            return idempotency_key_invalid(
                request,
                route,
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
        if response.status_code == 400 and isinstance(response.data, dict):
            return error_response(
                status_code=400,
                code="VALIDATION_ERROR",
                message="请求参数校验失败",
                details=response.data,
                request=self.request,
            )
        return response

    def post(self, request, asset_id):
        serializer = DownloadGrantRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = issue_fake_download_grant(
                actor_user_id=str(request.user.pk),
                portal=request.portal,
                asset_id=asset_id,
                use=serializer.validated_data["use"],
                idempotency_key=request.headers["Idempotency-Key"],
            )
        except IdempotencyKeyInvalid as error:
            return error_response(
                status_code=400,
                code="IDEMPOTENCY_KEY_INVALID",
                message="Idempotency-Key 必须为 1-255 个可见 ASCII 字符",
                details={"reason": str(error)},
                request=request,
            )
        except IdempotencyKeyConflict as error:
            return error_response(
                status_code=409,
                code="IDEMPOTENCY_KEY_CONFLICT",
                message="同一 Idempotency-Key 已用于不同请求",
                details={"reason": str(error)},
                request=request,
            )
        except IdempotencyStoreSaturated as error:
            return error_response(
                status_code=429,
                code="IDEMPOTENCY_STORE_SATURATED",
                message="幂等存储已达到活跃记录上限",
                details={"reason": str(error)},
                request=request,
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
                "asset_id": result.grant.asset_id,
                "one_time_token": result.grant.one_time_token,
                "expires_at": result.grant.expires_at.isoformat(),
                "max_uses": result.grant.max_uses,
            },
            status=201,
        )
        response["Cache-Control"] = "private, no-store"
        if result.replayed:
            response["X-Idempotent-Replay"] = "true"
        return response
