import ipaddress

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.core.http import error_response, idempotency_key_required, not_implemented
from apps.workspaces.serializers import (
    WorkspaceTokenVerifyRequestSerializer,
    WorkspaceTokenVerifyResponseSerializer,
)


@extend_schema(request=None, responses=None)
class WorkspaceSessionRouteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    route_template = ""

    def dispatch(self, request, *args, **kwargs):
        route = self.route_template.format(**kwargs)
        if not request.headers.get("Idempotency-Key"):
            return idempotency_key_required(request, route)
        request.b2_route = route
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, **kwargs):
        return not_implemented(request, "B4", request.b2_route)


@extend_schema(request=None, responses=None)
class WorkspaceSnapshotView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def put(self, request, public_id):
        return not_implemented(
            request,
            "B4",
            f"/api/v2/tasks/{public_id}/workspace-snapshot",
        )


@extend_schema(
    request=WorkspaceTokenVerifyRequestSerializer,
    responses=WorkspaceTokenVerifyResponseSerializer,
    exclude=True,
)
class WorkspaceTokenVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    request_serializer = WorkspaceTokenVerifyRequestSerializer
    response_serializer = WorkspaceTokenVerifyResponseSerializer

    def post(self, request):
        try:
            address = ipaddress.ip_address(request.META.get("REMOTE_ADDR", ""))
        except ValueError:
            address = None

        trusted = address is not None and any(
            address in network
            for network in settings.PORTAL_TRUSTED_PROXY_NETWORKS
        )
        if not trusted:
            return error_response(
                status_code=404,
                code="NOT_FOUND",
                message="资源不存在",
                details={},
                request=request,
            )

        return not_implemented(
            request,
            "B4",
            "/internal/workspace-tokens/verify",
        )
