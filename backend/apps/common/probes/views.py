from __future__ import annotations

from django.db import connection
from django.db.utils import DatabaseError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.common.portal.permissions import PlatformPortalAdminPermission
from apps.common.response import error_response, success_response
from apps.core.errors import DEPENDENCY_UNAVAILABLE

from .serializers import HealthResponseSerializer


class LiveHealthView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get_exception_handler(self):
        from apps.common.response.error import api_exception_handler

        return api_exception_handler

    @extend_schema(responses=HealthResponseSerializer, tags=["health"])
    def get(self, request):
        return success_response({"status": "ok"}, request)


class ReadyHealthView(LiveHealthView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(responses=HealthResponseSerializer, tags=["health"])
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            return error_response(
                code=DEPENDENCY_UNAVAILABLE.code,
                message="服务尚未就绪",
                request=request,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"database": "unavailable"},
                retryable=True,
            )
        return success_response(
            {"status": "ok", "checks": {"database": "ok"}},
            request,
        )


class PlatformHealthView(ReadyHealthView):
    allowed_portals = frozenset(("PLATFORM",))
    authentication_classes = ()
    permission_classes = (PlatformPortalAdminPermission,)

    @extend_schema(responses=HealthResponseSerializer, tags=["platform"])
    def get(self, request):
        return super().get(request)
