import ipaddress

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.http import error_response, idempotency_key_required
from apps.workspaces.serializers import (
    WorkspaceSessionCreateRequestSerializer,
    WorkspaceSessionCreateResponseSerializer,
    WorkspaceSessionRenewRequestSerializer,
    WorkspaceSessionRenewResponseSerializer,
    WorkspaceSessionRevokeRequestSerializer,
    WorkspaceSessionRevokeResponseSerializer,
    WorkspaceSnapshotRequestSerializer,
    WorkspaceSnapshotResponseSerializer,
    WorkspaceTokenVerifyRequestSerializer,
    WorkspaceTokenVerifyResponseSerializer,
)
from apps.workspaces.services import (
    WorkspaceServiceError,
    issue_workspace_session,
    renew_workspace_session,
    revoke_workspace_session,
    save_workspace_snapshot,
    verify_workspace_token,
    workspace_service_error_response,
)


class WorkspaceSessionCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=WorkspaceSessionCreateRequestSerializer,
        responses=WorkspaceSessionCreateResponseSerializer,
    )
    def post(self, request, public_id):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return idempotency_key_required(
                request,
                f"/api/v2/tasks/{public_id}/workspace-sessions",
            )

        serializer = WorkspaceSessionCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = issue_workspace_session(
                request=request,
                task_public_id=public_id,
                student_public_id=serializer.validated_data["student_public_id"],
                instance_public_id=serializer.validated_data["instance_public_id"],
                idempotency_key=idempotency_key,
            )
        except WorkspaceServiceError as error:
            return workspace_service_error_response(request, error)

        response = Response(result, status=201)
        response["Cache-Control"] = "private, no-store"
        return response


class WorkspaceSessionRenewView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=WorkspaceSessionRenewRequestSerializer,
        responses=WorkspaceSessionRenewResponseSerializer,
    )
    def post(self, request, public_id):
        serializer = WorkspaceSessionRenewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = renew_workspace_session(
                session_public_id=public_id,
                task_public_id=serializer.validated_data["task_public_id"],
                student_public_id=serializer.validated_data["student_public_id"],
                instance_public_id=serializer.validated_data["instance_public_id"],
            )
        except WorkspaceServiceError as error:
            return workspace_service_error_response(request, error)

        response = Response(result)
        response["Cache-Control"] = "private, no-store"
        return response


class WorkspaceSessionRevokeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=WorkspaceSessionRevokeRequestSerializer,
        responses=WorkspaceSessionRevokeResponseSerializer,
    )
    def post(self, request, public_id):
        serializer = WorkspaceSessionRevokeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = revoke_workspace_session(
                session_public_id=public_id,
                student_public_id=serializer.validated_data["student_public_id"],
            )
        except WorkspaceServiceError as error:
            return workspace_service_error_response(request, error)

        return Response(result)


class WorkspaceSnapshotView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=WorkspaceSnapshotRequestSerializer,
        responses=WorkspaceSnapshotResponseSerializer,
    )
    def put(self, request, public_id):
        serializer = WorkspaceSnapshotRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = save_workspace_snapshot(
                request=request,
                task_public_id=public_id,
                client_seq=serializer.validated_data["client_seq"],
                payload=serializer.validated_data.get("payload", {}),
            )
        except WorkspaceServiceError as error:
            return workspace_service_error_response(request, error)

        return Response(result)


@extend_schema(
    request=WorkspaceTokenVerifyRequestSerializer,
    responses=WorkspaceTokenVerifyResponseSerializer,
    exclude=True,
)
class WorkspaceTokenVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not self._is_trusted_source(request):
            return self._not_found(request)

        serializer = WorkspaceTokenVerifyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = verify_workspace_token(
            token_hash=serializer.validated_data["token_hash"],
            task_public_id=serializer.validated_data["task_public_id"],
            student_public_id=serializer.validated_data["student_public_id"],
            instance_public_id=serializer.validated_data["instance_public_id"],
        )
        response = Response(result)
        response["Cache-Control"] = "private, no-store"
        return response

    @staticmethod
    def _is_trusted_source(request) -> bool:
        try:
            address = ipaddress.ip_address(request.META.get("REMOTE_ADDR", ""))
        except ValueError:
            return False
        return any(
            address in network
            for network in settings.PORTAL_TRUSTED_PROXY_NETWORKS
        )

    @staticmethod
    def _not_found(request) -> Response:
        return error_response(
            status_code=404,
            code="NOT_FOUND",
            message="资源不存在",
            details={},
            request=request,
        )
