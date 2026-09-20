import ipaddress
import re
import uuid

from django.conf import settings
from django.http import JsonResponse


TRACEPARENT_PATTERN = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")


def portal_error_response(message: str, trace_id: str) -> JsonResponse:
    return JsonResponse(
        {
            "code": "PORTAL_CONTEXT_INVALID",
            "message": message,
            "details": {},
            "trace_id": trace_id,
        },
        status=400,
    )


def bad_request(request, exception=None):
    trace_id = getattr(request, "trace_id", str(uuid.uuid4()))
    return portal_error_response("请求上下文无效", trace_id)


def not_found(request, exception=None):
    return JsonResponse(
        {
            "code": "NOT_FOUND",
            "message": "资源不存在",
            "details": {},
            "trace_id": getattr(request, "trace_id", str(uuid.uuid4())),
        },
        status=404,
    )


def method_not_allowed(request, **kwargs):
    return JsonResponse(
        {
            "code": "METHOD_NOT_ALLOWED",
            "message": "HTTP 方法不被允许",
            "details": {},
            "trace_id": getattr(request, "trace_id", str(uuid.uuid4())),
        },
        status=405,
    )


class PortalContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        trace_id = self._trace_id(request)
        request.trace_id = trace_id
        if request.path in {"/health", "/internal/workspace-tokens/verify"}:
            request.portal = None
            return self.get_response(request)
        portal = self._portal(request)
        if portal is None:
            return portal_error_response("未识别可信 Host 或 portal，不猜测默认端", trace_id)
        request.portal = portal
        return self.get_response(request)

    @staticmethod
    def _trace_id(request) -> str:
        traceparent = request.headers.get("traceparent", "")
        if TRACEPARENT_PATTERN.fullmatch(traceparent.lower()):
            return traceparent.split("-")[2]
        return str(uuid.uuid4())

    @staticmethod
    def _is_trusted_proxy(request) -> bool:
        try:
            address = ipaddress.ip_address(request.META.get("REMOTE_ADDR", ""))
        except ValueError:
            return False
        return any(
            address in network
            for network in settings.PORTAL_TRUSTED_PROXY_NETWORKS
        )

    def _portal(self, request):
        host = request.get_host().split(":", 1)[0].lower()
        host_portals = [
            portal
            for portal, hosts in settings.PORTAL_HOST_MAP.items()
            if host in hosts
        ]
        if not host_portals:
            return None

        supplied_portal = request.headers.get("X-Portal") if self._is_trusted_proxy(request) else None
        if supplied_portal not in {"USER", "TEACHING", "PLATFORM"}:
            return None
        if supplied_portal != host_portals[0]:
            return None
        return supplied_portal
