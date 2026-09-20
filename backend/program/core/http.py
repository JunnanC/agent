"""Minimal HTTP context helpers shared by platform routes."""

from __future__ import annotations

from ipaddress import ip_address
from typing import Any

from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import SessionAuthentication

from core.response.error import ApiError


class SessionCSRFAuthentication(SessionAuthentication):
    """Session authentication with a stable CSRF failure error code."""

    class CSRFRequired(ApiError):
        status_code = 403
        default_code = "CSRF_REQUIRED"
        default_detail = "缺少或无效的 CSRF token"

    def enforce_csrf(self, request):
        try:
            super().enforce_csrf(request)
        except exceptions.PermissionDenied as exc:
            raise self.CSRFRequired() from exc


def resolve_portal(request: Any) -> str | None:
    """Resolve the trusted portal context for a request.

    X-Portal is trusted only when the direct peer is in the configured proxy
    network; otherwise the portal is derived from the trusted Host mapping.
    """
    header_portal = request.headers.get("X-Portal", "").upper()
    remote_addr = request.META.get("REMOTE_ADDR", "")
    try:
        remote_ip = ip_address(remote_addr)
        from_proxy = any(
            remote_ip in network
            for network in settings.PORTAL_TRUSTED_PROXY_NETWORKS
        )
    except ValueError:
        from_proxy = False

    if from_proxy and header_portal in settings.PORTAL_HOST_MAP:
        return header_portal

    host = request.get_host().rsplit(":", 1)[0].lower()
    for portal, hosts in settings.PORTAL_HOST_MAP.items():
        if host in {item.lower() for item in hosts}:
            return portal
    return None
