from __future__ import annotations

from django.db import transaction

from .models import TeamMembership, TeamSettings
from .services import _publish_session_revocation


class MembershipIdentityProvider:
    def get_membership(self, user_id: int) -> dict[str, str] | None:
        membership = TeamMembership.objects.filter(user_id=user_id).only("id", "status").first()
        if membership is None:
            return None
        return {"membership_id": str(membership.id), "status": membership.status}

    def unverified_start_policy(self, membership_id: str) -> str:
        settings = TeamSettings.objects.filter(id=1).only("unverified_start_policy").first()
        return settings.unverified_start_policy if settings else "DENIED"

    def revoke_authentication_sessions(self, user_id: int) -> None:
        with transaction.atomic():
            _publish_session_revocation(None, user_id)
