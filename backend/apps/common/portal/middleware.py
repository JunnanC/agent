from __future__ import annotations

import socket

from django.conf import settings
from django.http import HttpRequest

from apps.common.response.error import _django_error


class PortalContextMiddleware:
    """Resolve the portal from a known Host and, in production, a trusted gateway."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if not request.path.startswith("/api/v1/"):
            return self.get_response(request)

        host = request.get_host().split(":", 1)[0].lower()
        expected = settings.PORTAL_HOST_MAP.get(host)
        supplied = request.headers.get("X-Portal", "").strip().upper()
        if expected is None:
            return _django_error(
                request, code="PORTAL_UNKNOWN", message="无法识别当前访问入口", status_code=400
            )
        if settings.PORTAL_TRUST_PROXY_ENABLED:
            trusted = set(settings.PORTAL_TRUSTED_PROXY_IPS)
            # Swarm task addresses change on deployment; resolve only configured internal services.
            for proxy_host in settings.PORTAL_TRUSTED_PROXY_HOSTS:
                try:
                    trusted.update(info[4][0] for info in socket.getaddrinfo(proxy_host, None))
                except socket.gaierror:
                    continue
            if request.META.get("REMOTE_ADDR") not in trusted:
                return _django_error(
                    request, code="PORTAL_UNKNOWN", message="请求必须经过可信入口", status_code=400
                )
            if supplied != expected:
                return _django_error(
                    request, code="PORTAL_ACCESS_DENIED", message="当前入口无权访问该资源",
                    status_code=403,
                )
        elif supplied and supplied != expected:
            return _django_error(
                request, code="PORTAL_ACCESS_DENIED", message="当前入口无权访问该资源",
                status_code=403,
            )
        request.portal = expected
        return self.get_response(request)
