#!/usr/bin/env python
"""后端只读契约校验脚本。详细使用说明见 docs/check-contracts.md。"""

from __future__ import annotations

import argparse
import ast
import importlib
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.core.exceptions import ImproperlyConfigured

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKEND_DIR = (
    Path.cwd() if (Path.cwd() / "manage.py").is_file() else REPO_ROOT / "backend"
)
DEFAULT_SETTINGS = "config.settings.test"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


@dataclass(frozen=True)
class Result:
    status: str
    name: str
    detail: str = ""


class Report:
    def __init__(self) -> None:
        self.results: list[Result] = []

    def add(self, status: str, name: str, detail: str = "") -> None:
        self.results.append(Result(status, name, detail))
        suffix = f" | {detail}" if detail else ""
        print(f"[{status}] {name}{suffix}")

    def pass_(self, name: str, detail: str = "") -> None:
        self.add("PASS", name, detail)

    def warn(self, name: str, detail: str = "") -> None:
        self.add("WARN", name, detail)

    def fail(self, name: str, detail: str = "") -> None:
        self.add("FAIL", name, detail)

    @property
    def failed(self) -> int:
        return sum(result.status == "FAIL" for result in self.results)

    @property
    def warned(self) -> int:
        return sum(result.status == "WARN" for result in self.results)


def module_name(path: Path, backend_dir: Path) -> str:
    relative = path.relative_to(backend_dir).with_suffix("")
    return ".".join(relative.parts)


def is_task_decorator(decorator: ast.expr) -> bool:
    expression = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(expression, ast.Name):
        return expression.id in {"task", "shared_task"}
    if isinstance(expression, ast.Attribute):
        return expression.attr == "task"
    return False


def explicit_task_name(decorator: ast.expr) -> str | None:
    if not isinstance(decorator, ast.Call):
        return None
    for keyword in decorator.keywords:
        if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
            value = keyword.value.value
            if isinstance(value, str):
                return value
    return None


def discover_task_definitions(backend_dir: Path) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    apps_dir = backend_dir / "apps"
    for path in apps_dir.rglob("*.py"):
        if not path.is_file() or "tests" in path.parts or "migrations" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        package = module_name(path, backend_dir)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(
                is_task_decorator(decorator) for decorator in node.decorator_list
            ):
                continue
            explicit = next(
                (
                    name
                    for decorator in node.decorator_list
                    if (name := explicit_task_name(decorator))
                ),
                None,
            )
            definitions.append(
                {
                    "name": explicit or f"{package}.{node.name}",
                    "function": node.name,
                    "module": package,
                    "path": path,
                    "in_tasks_py": path.name == "tasks.py",
                }
            )
    return definitions


def normalize_route(route: str) -> str:
    return re.sub(r"<[^:>]+:[^>]+>", "<param>", route)


def view_name(callback: Any) -> str:
    view_class = getattr(callback, "view_class", None)
    if view_class is not None:
        return f"{view_class.__module__}.{view_class.__qualname__}"
    return f"{getattr(callback, '__module__', '')}.{getattr(callback, '__qualname__', callback)}"


def collect_routes(backend_dir: Path) -> tuple[list[tuple[str, str, str]], str | None]:
    import django
    from django.urls import URLPattern, URLResolver, get_resolver

    django.setup()
    routes: list[tuple[str, str, str]] = []

    def walk(patterns: list[Any]) -> None:
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                walk(pattern.url_patterns)
            elif isinstance(pattern, URLPattern):
                route = str(pattern.pattern)
                routes.append(
                    (route, str(pattern.name or ""), view_name(pattern.callback))
                )

    try:
        walk(get_resolver().url_patterns)
    except (
        ImportError,
        AttributeError,
        TypeError,
        ValueError,
        ImproperlyConfigured,
    ) as exc:
        return [], f"{type(exc).__name__}: {exc}"
    return routes, None


def check_routes(report: Report, backend_dir: Path) -> None:
    print("\n=== 路由契约 ===")
    routes, error = collect_routes(backend_dir)
    if error:
        report.fail("路由可解析", error)
        return

    duplicates = {
        route for route, _, _ in routes if sum(item[0] == route for item in routes) > 1
    }
    if duplicates:
        report.fail("路径不重复", "重复路径: " + ", ".join(sorted(duplicates)))
    else:
        report.pass_("路径不重复", f"{len(routes)} 条路由")

    shapes: dict[str, set[str]] = defaultdict(set)
    for route, _, _ in routes:
        shapes[normalize_route(route)].add(route)
    shadows = {shape for shape, values in shapes.items() if len(values) > 1}
    if shadows:
        report.fail("路径形状不互相遮蔽", "遮蔽形状: " + ", ".join(sorted(shadows)))
    else:
        report.pass_("路径形状不互相遮蔽", "无遮蔽")

    print("路由登记表:")
    for index, (route, name, callback) in enumerate(routes, start=1):
        print(f"  {index:02d}. {route:<55} {name:<28} {callback}")


def find_error_code_modules(backend_dir: Path) -> list[Path]:
    roots = [backend_dir / "apps", backend_dir / "education_experiment_platform"]
    modules: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if (
                not path.is_file()
                or "tests" in path.parts
                or "__pycache__" in path.parts
            ):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError):
                continue
            names = {
                node.targets[0].id
                for node in tree.body
                if isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
            }
            classes = {
                node.name for node in tree.body if isinstance(node, ast.ClassDef)
            }
            if "ERROR_CODES" in names and "ErrorCode" in classes:
                modules.append(path)
    return modules


def member_code(member: Any) -> int | None:
    code = getattr(member, "code", None)
    if isinstance(code, int):
        return code
    if isinstance(member.value, int):
        return member.value
    return None


def member_http_status(member: Any) -> int | None:
    for attribute in ("http_status", "status_code", "http"):
        value = getattr(member, attribute, None)
        if isinstance(value, int):
            return value
    return None


def normalize_error_registry(registry: Any) -> dict[int, Any]:
    normalized: dict[int, Any] = {}
    if isinstance(registry, dict):
        for key, value in registry.items():
            if isinstance(key, int):
                normalized[key] = value
            elif isinstance(value, int):
                normalized[value] = key
    return normalized


def check_error_codes(report: Report, backend_dir: Path) -> None:
    print("\n=== 错误码契约 ===")
    paths = find_error_code_modules(backend_dir)
    if not paths:
        report.fail(
            "存在集中错误码登记", "未找到同时定义 ErrorCode 与 ERROR_CODES 的模块"
        )
        return

    all_members: list[Any] = []
    registered_values: list[int] = []
    prefix_drifts: list[str] = []
    try:
        for path in paths:
            module = importlib.import_module(module_name(path, backend_dir))
            error_type = getattr(module, "ErrorCode", None)
            registry = normalize_error_registry(getattr(module, "ERROR_CODES", {}))
            if error_type is None:
                report.fail("错误码模块可导入", f"{path} 缺少 ErrorCode")
                continue
            try:
                members = list(error_type)
            except TypeError:
                members = []
            all_members.extend(members)
            registered_values.extend(registry)
            registered_members = set(registry.values())

            for member in members:
                symbol = getattr(member, "symbol", member.name)
                if member.name != symbol:
                    report.fail(
                        "常量名与 ErrorCode.symbol 一致", f"{member.name} != {symbol}"
                    )
                if member not in registered_members:
                    report.fail(
                        "ErrorCode 已登记进 ERROR_CODES", f"{member.name} 未登记"
                    )
                code = member_code(member)
                http_status = member_http_status(member)
                if (
                    code is not None
                    and http_status is not None
                    and code // 100 != http_status
                ):
                    prefix_drifts.append(f"{member.name}={code}/http={http_status}")
    except (
        ImportError,
        AttributeError,
        TypeError,
        ValueError,
        ImproperlyConfigured,
    ) as exc:
        report.fail("错误码模块可导入", f"{type(exc).__name__}: {exc}")
        return

    duplicate_codes = [
        str(code) for code, count in Counter(registered_values).items() if count > 1
    ]
    if duplicate_codes:
        report.fail("错误码数值唯一", "重复数值: " + ", ".join(duplicate_codes))
    else:
        report.pass_("错误码数值唯一", f"{len(registered_values)} 个错误码")

    if prefix_drifts:
        report.warn("错误码前缀与 HTTP 状态一致", "; ".join(prefix_drifts))
    else:
        report.pass_("错误码前缀与 HTTP 状态一致")


def check_models(report: Report, backend_dir: Path) -> None:
    import django
    from django.apps import apps

    print("\n=== 模型契约 ===")
    if not apps.ready:
        django.setup()
    app_models = [
        model
        for app_config in apps.get_app_configs()
        if Path(app_config.path).is_relative_to(backend_dir / "apps")
        for model in app_config.get_models()
    ]
    if not app_models:
        report.warn("业务模型存在", "当前 apps 下没有业务模型")
        return

    unmanaged = [model for model in app_models if model._meta.managed is False]
    if len(unmanaged) != len(app_models):
        managed_names = [
            f"{model._meta.label}"
            for model in app_models
            if model._meta.managed is not False
        ]
        report.fail("业务模型全部 managed=False", ", ".join(managed_names))
    else:
        report.pass_("业务模型全部 managed=False", f"{len(app_models)} 个模型")

    tables: dict[str, str] = {}
    conflicts: list[str] = []
    for model in app_models:
        table = model._meta.db_table
        if table in tables:
            conflicts.append(f"{table}: {tables[table]} / {model._meta.label}")
        else:
            tables[table] = model._meta.label
    if conflicts:
        report.fail("db_table 不冲突", "; ".join(conflicts))
    else:
        report.pass_("db_table 不冲突", f"{len(tables)} 个表名")


def check_migrations(report: Report, backend_dir: Path) -> None:
    print("\n=== 迁移红线 ===")
    migration_files = [
        path
        for path in (backend_dir / "apps").glob("*/migrations/*.py")
        if path.name != "__init__.py"
    ]
    if migration_files:
        report.fail(
            "apps/*/migrations/ 无迁移文件",
            ", ".join(str(path.relative_to(backend_dir)) for path in migration_files),
        )
    else:
        report.pass_("apps/*/migrations/ 无迁移文件", "无迁移文件")


def queue_from_route(route: Any) -> str | None:
    if isinstance(route, str):
        return route
    if isinstance(route, dict):
        queue = route.get("queue")
        return queue if isinstance(queue, str) else None
    return (
        getattr(route, "name", None)
        if isinstance(getattr(route, "name", None), str)
        else None
    )


def check_celery(report: Report, backend_dir: Path) -> None:
    import django
    from django.conf import settings

    print("\n=== Celery 契约 ===")
    if not apps_ready():
        django.setup()

    configured_queues = getattr(settings, "CELERY_TASK_QUEUES", None) or {}
    queues = (
        list(configured_queues)
        if isinstance(configured_queues, dict)
        else [getattr(queue, "name", str(queue)) for queue in configured_queues]
    )
    default_queue = getattr(settings, "CELERY_TASK_DEFAULT_QUEUE", "")
    if not queues:
        report.fail("已声明队列且包含默认队列", "queues=[]")
    elif default_queue not in queues:
        report.fail(
            "已声明队列且包含默认队列", f"queues={queues} default={default_queue}"
        )
    else:
        report.pass_(
            "已声明队列且包含默认队列", f"queues={queues} default={default_queue}"
        )

    routes = getattr(settings, "CELERY_TASK_ROUTES", {}) or {}
    route_targets = [
        queue
        for value in (routes.values() if isinstance(routes, dict) else [])
        if (queue := queue_from_route(value))
    ]
    undeclared_routes = sorted(set(route_targets) - set(queues))
    if undeclared_routes:
        report.fail("路由目标队列已声明", "未声明: " + ", ".join(undeclared_routes))
    else:
        report.pass_("路由目标队列已声明", f"{len(route_targets)} 条显式路由")

    task_definitions = discover_task_definitions(backend_dir)
    explicit_names = [
        definition["name"]
        for definition in task_definitions
        if definition["name"]
        not in {
            f"{definition['module']}.{definition['function']}"
            for definition in task_definitions
        }
    ]
    duplicate_names = [
        name for name, count in Counter(explicit_names).items() if count > 1
    ]
    if duplicate_names:
        report.fail("显式任务名不重复", ", ".join(duplicate_names))
    else:
        report.pass_("显式任务名不重复", f"{len(explicit_names)} 个显式名")

    try:
        project_package = settings.SETTINGS_MODULE.split(".", 1)[0]
        celery_module = importlib.import_module(f"{project_package}.celery")
        celery_app = celery_module.app
        celery_app.loader.import_default_modules()
        registered_tasks = set(celery_app.tasks)
    except (
        ImportError,
        AttributeError,
        TypeError,
        ValueError,
        ImproperlyConfigured,
    ) as exc:
        report.fail("Celery app 可导入", f"{type(exc).__name__}: {exc}")
        return

    outside_tasks = [
        definition for definition in task_definitions if not definition["in_tasks_py"]
    ]
    unregistered_outside = [
        definition["name"]
        for definition in outside_tasks
        if definition["name"] not in registered_tasks
    ]
    if unregistered_outside:
        report.fail("tasks.py 之外的任务必须已注册", ", ".join(unregistered_outside))
    else:
        report.pass_("tasks.py 之外的任务必须已注册", f"{len(outside_tasks)} 个")

    unrouted = [
        definition["name"]
        for definition in task_definitions
        if definition["name"] not in routes
    ]
    if unrouted:
        report.warn("任务显式路由", "未显式路由: " + ", ".join(unrouted))
    else:
        report.pass_("任务显式路由", f"{len(task_definitions)} 个任务")

    beat = getattr(settings, "CELERY_BEAT_SCHEDULE", {}) or {}
    entries = list(beat.values()) if isinstance(beat, dict) else list(beat)
    if not entries:
        report.fail("beat 非空（否则 Outbox 永不投递）", "entries=[]")
        return
    beat_tasks = [
        entry.get("task", "") if isinstance(entry, dict) else str(entry)
        for entry in entries
    ]
    missing_beat_tasks = [task for task in beat_tasks if task not in registered_tasks]
    if missing_beat_tasks:
        report.fail("beat 引用已注册任务", ", ".join(missing_beat_tasks))
    else:
        report.pass_("beat 非空且引用已注册任务", f"entries={beat_tasks}")


def apps_ready() -> bool:
    from django.apps import apps

    return apps.ready


def service_block(lines: list[str], service: str) -> list[str]:
    start = None
    indent = 0
    for index, line in enumerate(lines):
        match = re.match(rf"^(\s+){re.escape(service)}:\s*$", line)
        if match:
            start = index + 1
            indent = len(match.group(1))
            break
    if start is None:
        return []
    block: list[str] = []
    for line in lines[start:]:
        if line.strip() and not line.startswith(" " * (indent + 1)):
            break
        block.append(line)
    return block


def parse_command_queues(block: list[str]) -> list[str] | None:
    command = ""
    for index, line in enumerate(block):
        if re.match(r"^\s*command:\s*", line):
            inline = line.split(":", 1)[1].strip()
            if inline:
                command = inline
            else:
                command_indent = len(line) - len(line.lstrip())
                parts: list[str] = []
                for nested in block[index + 1 :]:
                    if not nested.strip():
                        continue
                    nested_indent = len(nested) - len(nested.lstrip())
                    if nested_indent <= command_indent:
                        break
                    parts.append(nested.strip().lstrip("- ").strip("\"'"))
                command = " ".join(parts)
            break
    if not command:
        return None
    if command.startswith("[") and command.endswith("]"):
        try:
            parsed_command = ast.literal_eval(command)
            tokens = [str(item) for item in parsed_command]
        except (SyntaxError, ValueError):
            tokens = command.split()
    else:
        tokens = command.split()
    for index, token in enumerate(tokens):
        if token in {"-Q", "--queues"} and index + 1 < len(tokens):
            return [item for item in tokens[index + 1].split(",") if item]
        if token.startswith(("--queues=", "-Q=")):
            return [item for item in token.split("=", 1)[1].split(",") if item]
    return None


def parse_environment_queues(block: list[str]) -> list[str] | None:
    for index, line in enumerate(block):
        if "CELERY_TASK_QUEUES:" not in line:
            continue
        inline = line.split(":", 1)[1].strip().strip("\"'")
        if inline:
            return [item.strip() for item in inline.split(",") if item.strip()]
        values: list[str] = []
        env_indent = len(line) - len(line.lstrip())
        for nested in block[index + 1 :]:
            if not nested.strip():
                continue
            nested_indent = len(nested) - len(nested.lstrip())
            if nested_indent <= env_indent:
                break
            value = nested.strip().lstrip("- ").strip("\"'")
            if value:
                values.extend(item.strip() for item in value.split(",") if item.strip())
        return values or None
    return None


def check_compose(report: Report, settings_queues: list[str]) -> None:
    print("\n=== 部署件一致性 ===")
    for filename in ("docker-compose.yml", "docker-compose.prod.yml"):
        path = REPO_ROOT / filename
        if not path.is_file():
            report.fail(f"{filename} 的 worker 声明 -Q", "文件不存在")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        worker = service_block(lines, "worker")
        if not worker:
            report.fail(f"{filename} 的 worker 声明 -Q", "未找到 worker 服务")
            continue
        worker_queues = parse_command_queues(worker)
        if worker_queues is None:
            report.fail(
                f"{filename} 的 worker 声明 -Q", "未找到 -Q：worker 只会消费默认队列"
            )
            continue
        env_queues = parse_environment_queues(worker)
        if env_queues is not None and set(worker_queues) != set(env_queues):
            report.fail(
                f"{filename} 的 -Q 与 CELERY_TASK_QUEUES 一致",
                f"-Q={worker_queues} env={env_queues}",
            )
        elif set(worker_queues) != set(settings_queues):
            report.fail(
                f"{filename} 的 -Q 与 settings.CELERY_TASK_QUEUES 一致",
                f"-Q={worker_queues} settings={settings_queues}",
            )
        else:
            report.pass_(
                f"{filename} 的 -Q 与 CELERY_TASK_QUEUES 一致",
                f"-Q={worker_queues} "
                + (
                    f"env={env_queues}"
                    if env_queues is not None
                    else f"settings={settings_queues}"
                ),
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend-dir",
        type=Path,
        default=DEFAULT_BACKEND_DIR,
        help="后端目录，默认自动识别仓库根目录下的 backend",
    )
    parser.add_argument(
        "--settings",
        default=DEFAULT_SETTINGS,
        help="Django settings 模块，默认 config.settings.test",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backend_dir = args.backend_dir.resolve()
    if not (backend_dir / "manage.py").is_file():
        print(f"backend directory not found: {backend_dir}", file=sys.stderr)
        return 2

    sys.path.insert(0, str(backend_dir))
    os.environ["DJANGO_SETTINGS_MODULE"] = args.settings
    if not os.environ.get("SECRET_KEY"):
        os.environ["SECRET_KEY"] = "contract-check"

    from django.conf import settings

    settings._setup()
    configured_queues = getattr(settings, "CELERY_TASK_QUEUES", {}) or {}
    settings_queues = (
        list(configured_queues)
        if isinstance(configured_queues, dict)
        else [getattr(queue, "name", str(queue)) for queue in configured_queues]
    )

    report = Report()
    check_routes(report, backend_dir)
    check_error_codes(report, backend_dir)
    check_models(report, backend_dir)
    check_migrations(report, backend_dir)
    check_celery(report, backend_dir)
    check_compose(report, settings_queues)

    print("\n=== 汇总 ===")
    print(f"PASS={sum(result.status == 'PASS' for result in report.results)}")
    print(f"WARN={report.warned}")
    print(f"FAIL={report.failed}")
    if report.failed:
        print(f"FAILED: {report.failed} 项未通过")
        return 1
    print(f"ALL PASS（{report.warned} 项提示）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
