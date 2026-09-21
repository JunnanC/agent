from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    ErrorEnvelopeSerializer,
    HealthResponseSerializer,
    ReadinessResponseSerializer,
)


class HealthView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        tags=["system"],
        summary="Process liveness",
        responses={200: HealthResponseSerializer},
        extensions={"x-portals": ["USER", "TEACHING", "PLATFORM"]},
    )
    def get(self, request: Request) -> Response:
        return Response({
            "data": {
                "status": "ok",
                "service": "django",
                "version": settings.APP_VERSION,
                "openapi_revision": settings.OPENAPI_REVISION,
                "git_revision": settings.GIT_REVISION,
                "portal": getattr(request, "portal", None),
            },
            "meta": {"trace_id": getattr(request, "trace_id", "")},
        })


class ReadinessView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        tags=["system"],
        summary="MySQL readiness",
        responses={200: ReadinessResponseSerializer, 503: ErrorEnvelopeSerializer},
        extensions={"x-portals": ["USER", "TEACHING", "PLATFORM"]},
    )
    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            return Response(
                {
                    "error": {
                        "code": "DATABASE_UNAVAILABLE",
                        "message": "数据库尚未就绪",
                        "detail": {},
                        "trace_id": getattr(request, "trace_id", ""),
                        "retryable": True,
                    }
                },
                status=503,
            )
        return Response({
            "data": {"status": "ready", "checks": {"mysql": "ok"}},
            "meta": {"trace_id": getattr(request, "trace_id", "")},
        })
