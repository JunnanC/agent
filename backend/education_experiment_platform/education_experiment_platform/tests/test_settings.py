from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase

EXPECTED_DOMAIN_APPS = {
    "core",
    "accounts",
    "courses",
    "governance",
    "labtemplates",
    "experiments",
    "provisioning",
    "workspaces",
    "reports",
    "reviews",
    "archives",
    "agents",
    "notifications",
    "analytics",
    "integrations",
}


class SettingsTests(SimpleTestCase):
    def test_all_target_apps_exist_without_teams(self) -> None:
        installed = {config.label for config in apps.get_app_configs()}
        assert installed >= EXPECTED_DOMAIN_APPS
        assert "teams" not in installed

    def test_contract_revision_and_api_prefix_are_fixed(self) -> None:
        assert settings.OPENAPI_REVISION == "v2-p00"

    def test_p00_domain_apps_have_no_models(self) -> None:
        for app_label in EXPECTED_DOMAIN_APPS:
            assert list(apps.get_app_config(app_label).get_models()) == []
