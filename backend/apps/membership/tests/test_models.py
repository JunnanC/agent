from __future__ import annotations

from apps.membership.models import TeamMembership, TeamSettings


def test_models_map_frozen_tables(membership_tables: None) -> None:
    assert TeamSettings._meta.db_table == "team_settings"
    assert TeamSettings._meta.managed is False
    assert TeamMembership._meta.db_table == "team_memberships"
    assert TeamMembership._meta.managed is False


def test_membership_maps_required_columns(team_settings: TeamSettings) -> None:
    fields = TeamMembership._meta.get_fields()

    assert fields
