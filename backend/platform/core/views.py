from __future__ import annotations

from django.db import connection
from django.db.utils import DatabaseError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.views import APIView

from core.responses import error_response, success_response
from core.serializers import HealthResponseSerializer


class LiveHealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def get(self, request):
        return success_response({"status": "ok"}, request)


class ReadyHealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            return error_response(
                code="SERVICE_NOT_READY",
                message="服务尚未就绪",
                request=request,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"database": "unavailable"},
                retryable=True,
            )
        return success_response(
            {"status": "ok", "checks": {"database": "ok"}}, request,
        )


class PlatformHealthView(ReadyHealthView):
    authentication_classes = APIView.authentication_classes
    permission_classes = [IsAdminUser]

    @extend_schema(tags=["platform"], responses=HealthResponseSerializer)
    def get(self, request):
        return super().get(request)
