from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from common.response.error import _django_error

from . import PORTALS


class PortalContextMiddleware:
    """Resolve and validate the trusted portal for v2 API requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not request.path.startswith("/api/v2/"):
            return self.get_response(request)

        host = request.get_host().split(":", 1)[0].lower()
        expected = settings.PORTAL_HOST_MAP.get(host)
        supplied = request.headers.get("X-Portal", "").strip().upper()
        trusted_source = request.META.get("REMOTE_ADDR") in settings.PORTAL_TRUSTED_PROXY_IPS

        if expected is None:
            return _django_error(request, code="PORTAL_REQUIRED", message="无法识别当前访问入口", status_code=400)
        if settings.PORTAL_TRUST_PROXY_ENABLED and not trusted_source:
            return _django_error(request, code="PORTAL_REQUIRED", message="请求必须经过可信入口", status_code=400)
        portal = supplied if settings.PORTAL_TRUST_PROXY_ENABLED else (supplied or expected)
        if portal not in PORTALS or (settings.PORTAL_REQUIRE_HOST_MATCH and portal != expected):
            return _django_error(request, code="PORTAL_ACCESS_DENIED", message="当前入口无权访问该资源", status_code=403)

        request.portal = portal
        return self.get_response(request)
