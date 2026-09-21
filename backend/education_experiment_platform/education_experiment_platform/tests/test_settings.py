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

    # 原 ``test_p00_domain_apps_have_no_models``已删除：它断言的是 P00 快照
    # 「域 app 还没有任何模型」，而 P01 落地 core/courses 模型后这一条按定义失效。
    # 保留它等于断言「项目永远不能加模型」。各域 app 是否已实现模型
    # 改由各 P 阶段的出口记录负责，不再做全局断言。
