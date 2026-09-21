from rest_framework.permissions import BasePermission


class PortalPermission(BasePermission):
    """Allow a view to declare the portals from which it is reachable."""

    required_portals = frozenset()

    def has_permission(self, request, view):
        portal = getattr(request, "portal", None)
        allowed = getattr(view, "allowed_portals", self.required_portals)
        return portal is not None and (not allowed or portal in allowed)
