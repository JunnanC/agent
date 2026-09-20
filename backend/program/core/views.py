"""HTTP adapters for core object-asset routes."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from core.http import SessionCSRFAuthentication, resolve_portal
from core.response import created_response, error_response
from core.serializers import DownloadGrantRequestSerializer
from core.services import (
    DownloadDenied,
    ObjectAssetNotFound,
    PortalRequired,
    download_grant_service,
)


class DownloadGrantView(APIView):
    authentication_classes = [SessionCSRFAuthentication]
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        response.headers["Cache-Control"] = "no-store"
        return response

    def post(self, request, asset_id: str):
        serializer = DownloadGrantRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            grant = download_grant_service.issue(
                actor_user_id=str(request.user.pk),
                portal=resolve_portal(request),
                asset_id=asset_id,
                use=serializer.validated_data["use"],
            )
        except PortalRequired:
            return error_response(
                code="PORTAL_REQUIRED",
                message="无法确定可信门户",
                request=request,
                status_code=status.HTTP_403_FORBIDDEN,
            )
        except ObjectAssetNotFound:
            return error_response(
                code="RESOURCE_NOT_FOUND",
                message="资源不存在",
                request=request,
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except DownloadDenied as exc:
            return error_response(
                code="DOWNLOAD_GRANT_DENIED",
                message="不允许下载该对象",
                request=request,
                status_code=status.HTTP_403_FORBIDDEN,
                details={"reason": exc.reason},
            )

        return created_response(
            {
                "asset_id": grant.asset_id,
                "one_time_token": grant.one_time_token,
                "expires_at": grant.expires_at.isoformat(),
                "max_uses": grant.max_uses,
            },
            request,
            headers={"Cache-Control": "no-store"},
        )


class FileDownloadView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, one_time_token: str):
        try:
            grant = download_grant_service.exchange(one_time_token=one_time_token)
        except DownloadDenied as exc:
            return error_response(
                code="DOWNLOAD_TOKEN_DENIED",
                message="下载 token 无效或不可用",
                request=request,
                status_code=status.HTTP_403_FORBIDDEN,
                details={"reason": exc.reason},
                headers={"Cache-Control": "no-store"},
            )

        return error_response(
            code="DOWNLOAD_STREAM_NOT_IMPLEMENTED",
            message="对象取流尚未接入",
            request=request,
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            details={
                "slice": "B5",
                "grant_id": grant.grant_id,
                "asset_id": grant.asset_id,
                "reason": "OBJECT_STREAM_PENDING",
            },
            headers={"Cache-Control": "no-store"},
        )
