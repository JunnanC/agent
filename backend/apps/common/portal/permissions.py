from rest_framework.permissions import BasePermission

from apps.common.providers import actor_role


class PortalPermission(BasePermission):
    """Portal is an additional boundary, never an account authorization replacement."""

    required_portals = frozenset()

    def has_permission(self, request, view):
        portal = getattr(request, "portal", None)
        allowed = getattr(view, "allowed_portals", self.required_portals)
        return portal is not None and (not allowed or portal in allowed)


class PlatformPortalAdminPermission(PortalPermission):
    required_portals = frozenset(("PLATFORM",))

    def has_permission(self, request, view):
        return super().has_permission(request, view) and actor_role(request) == "SYSTEM_ADMIN"
