#!/usr/bin/env python
"""后端契约校验：把评审依赖的约定落成可执行断言。

为什么需要这个脚本
------------------
后端有几类约定目前只靠人工评审保证。它们漂移时**不会立刻报错**，通常要到线上才暴露：

1. 路由路径重复：Django 按注册顺序匹配，后注册的那条永远不会命中，且不报错。
2. 错误码数值重复：``ERRORS_BY_CODE`` 由字典推导生成，同码后者静默覆盖前者，
   客户端拿到的错误语义会随定义顺序变化。
3. Celery 队列漏配：worker 默认只消费 ``CELERY_TASK_DEFAULT_QUEUE``，
   路由指向一个没人消费的队列时，任务是**静默积压**——既不报错也不执行。
4. 冻结库阶段产生迁移：本阶段模型全部 ``managed = False``，
   一旦有人 ``makemigrations``，就会把 ``V4.0`` 已有表写进 DDL。
5. 非 ``tasks.py`` 中定义的任务：``autodiscover_tasks()`` 只扫描 ``tasks.py``，
   定义在别处的任务必须被显式导入才存在，否则注册表里没有它。

本脚本只读，不修改任何文件。退出码 0 = 全部通过，1 = 存在 FAIL。

用法
----
    cd backend && python ../scripts/check-contracts.py
    python ../scripts/check-contracts.py --settings=config.settings.test
    python ../scripts/check-contracts.py --backend-dir=backend

默认设置模块是 ``config.settings.test``：它不连 MySQL（用 sqlite 覆盖 ``DATABASES``），
因此本脚本无需数据库即可运行。
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

DEFAULT_SETTINGS = "config.settings.test"
COMPOSE_FILES = ("docker-compose.yml", "docker-compose.prod.yml")

# 只匹配 Django 路由里的转换器段（例如 ``<int:membership_id>`` 与 ``<str:id>``），
# 用于识别「形状相同、只有转换器不同」的路由——它们会互相遮蔽。
ROUTE_PARAM_RE = re.compile(r"<[^<>]+>")
QUEUE_FLAG_RE = re.compile(r'"-Q",\s*"([^"]+)"')
TASK_DECORATORS = frozenset({"shared_task", "task"})


class Report:
    """收集断言结果。FAIL 决定退出码，WARN 只提示、不阻断。"""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        suffix = f" | {detail}" if detail else ""
        print(f"[{'PASS' if ok else 'FAIL'}] {name}{suffix}")
        if not ok:
            self.failures.append(name)
        return ok

    def warn(self, name: str, detail: str = "") -> None:
        suffix = f" | {detail}" if detail else ""
        print(f"[WARN] {name}{suffix}")
        self.warnings.append(name)

    def info(self, text: str) -> None:
        print(f"       {text}")


def _iter_routes(patterns, prefix: str = "") -> Iterator[tuple[str, object]]:
    """递归展开 urlpatterns，返回 (完整路径, pattern)。

    ``include()`` 会生成 URLResolver，其 ``pattern`` 是父级 ``path()`` 里的前缀，
    因此父级前缀 + 子级 pattern 拼接即为可匹配的完整路径。
    """
    from django.urls import URLResolver

    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _iter_routes(pattern.url_patterns, route)
        else:
            yield route, pattern


def check_routes(report: Report) -> None:
    from django.urls import get_resolver

    routes = [route for route, _ in _iter_routes(get_resolver().url_patterns)]
    report.info(f"注册路由 {len(routes)} 条")

    counts: dict[str, int] = {}
    for route in routes:
        counts[route] = counts.get(route, 0) + 1
    duplicated = {route: n for route, n in counts.items() if n > 1}
    report.check("路由路径不重复", not duplicated, f"重复={duplicated}")

    shapes: dict[str, set[str]] = {}
    for route in routes:
        shapes.setdefault(ROUTE_PARAM_RE.sub("<>", route), set()).add(route)
    shadowed = {shape: sorted(v) for shape, v in shapes.items() if len(v) > 1}
    report.check("路由形状不互相遮蔽", not shadowed, f"冲突={shadowed}")

    print("       —— 路由登记表 ——")
    for route in sorted(routes):
        print(f"       {route}")


def check_error_codes(report: Report) -> None:
    from apps.common import errors as errors_module

    registry = errors_module.ERROR_CODES
    by_code = errors_module.ERRORS_BY_CODE

    report.check(
        "错误码数值唯一（同码会静默覆盖）",
        len(registry) == len(by_code),
        f"symbol 数={len(registry)} 数值数={len(by_code)}",
    )

    mismatched = {name: value.symbol for name, value in registry.items() if name != value.symbol}
    report.check("常量名与 ErrorCode.symbol 一致", not mismatched, f"不一致={mismatched}")

    # 定义了 ErrorCode 却没登记进 ERROR_CODES 时，该错误码不会出现在解析表里，
    # 也不会有 symbol -> code 的映射，属于静默漏登记。
    defined = {
        name: value
        for name, value in vars(errors_module).items()
        if isinstance(value, errors_module.ErrorCode)
    }
    unregistered = sorted(set(defined) - set(registry))
    report.check("所有已定义的错误码都已登记", not unregistered, f"未登记={unregistered}")

    report.info(f"错误码 {len(registry)} 个，数值 {min(by_code)}~{max(by_code)}")

    # 既有编号约定是「数值前缀 = HTTP 状态」（40001 -> 400）。仓库中已有多处历史漂移
    # （例如 42212 对应 HTTP 403），属于已冻结事实，故只提示、不判失败。
    drifted = {
        name: f"code={value.code} http={value.http_status}"
        for name, value in registry.items()
        if value.http_status != value.code // 100
    }
    if drifted:
        report.warn("错误码数值前缀与 HTTP 状态不一致（既有漂移）", f"{drifted}")


def check_models(report: Report) -> None:
    from django.apps import apps as django_apps

    models = [
        model
        for model in django_apps.get_models()
        if not model.__module__.startswith("django.contrib.")
    ]

    managed = sorted(model._meta.label for model in models if model._meta.managed)
    report.check("业务模型全部 managed=False（不生成迁移）", not managed, f"managed=True={managed}")

    tables: dict[str, list[str]] = {}
    for model in models:
        tables.setdefault(model._meta.db_table, []).append(model._meta.label)
    clashed = {table: labels for table, labels in tables.items() if len(labels) > 1}
    report.check("模型表名不冲突", not clashed, f"冲突={clashed}")

    report.info(f"业务模型 {len(models)} 个，映射 {len(tables)} 张表")


def check_no_migrations(report: Report, backend_dir: Path) -> None:
    apps_dir = backend_dir / "apps"
    if not apps_dir.is_dir():
        report.check("apps 目录存在", False, str(apps_dir))
        return

    present: list[str] = []
    dirty: list[str] = []
    for app_dir in sorted(path for path in apps_dir.iterdir() if path.is_dir()):
        migrations = app_dir / "migrations"
        if not migrations.is_dir():
            continue
        present.append(app_dir.name)
        if any(path.name != "__init__.py" for path in migrations.glob("*.py")):
            dirty.append(app_dir.name)

    report.check("不存在 apps/*/migrations/ 迁移文件", not dirty, f"含迁移={dirty}")
    if present:
        report.warn("存在空的 apps/*/migrations/ 目录（本阶段不应出现）", f"{present}")


def _module_name(path: Path, backend_dir: Path) -> str:
    parts = list(path.relative_to(backend_dir).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _task_declarations(backend_dir: Path) -> list[tuple[Path, str, str | None]]:
    """静态扫描任务装饰器，返回 (文件, 函数名, 显式 name)。

    用 AST 而不是正则：装饰器可能跨行书写，正则容易漏。
    """
    roots = [backend_dir / "apps", backend_dir / "config"]
    files = sorted(path for root in roots if root.is_dir() for path in root.rglob("*.py"))

    declarations: list[tuple[Path, str, str | None]] = []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            print(f"[WARN] 无法解析 {path}: {exc}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if name not in TASK_DECORATORS:
                    continue
                explicit = None
                for keyword in decorator.keywords:
                    if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                        explicit = str(keyword.value.value)
                declarations.append((path, node.name, explicit))
    return declarations


def check_celery(report: Report, backend_dir: Path) -> None:
    from django.conf import settings

    from config.celery import app as celery_app

    declared = tuple(queue.name for queue in getattr(settings, "CELERY_TASK_QUEUES", ()))
    default_queue = getattr(settings, "CELERY_TASK_DEFAULT_QUEUE", "")
    report.check(
        "已声明队列且包含默认队列",
        bool(declared) and default_queue in declared,
        f"queues={list(declared)} default={default_queue}",
    )

    routes: dict[str, dict] = dict(getattr(settings, "CELERY_TASK_ROUTES", {}))
    undeclared = {
        task: config.get("queue")
        for task, config in routes.items()
        if config.get("queue") not in declared
    }
    report.check("路由目标队列均已声明", not undeclared, f"未声明={undeclared}")

    celery_app.loader.import_default_modules()
    registered = {name for name in celery_app.tasks if not name.startswith("celery.")}

    beat = dict(getattr(settings, "CELERY_BEAT_SCHEDULE", {}))
    check = report.check(
        "beat 非空（否则 Outbox 永不投递）",
        bool(beat),
        f"entries={sorted(beat)}",
    )
    if check:
        missing = {name: entry.get("task") for name, entry in beat.items()}
        missing = {name: task for name, task in missing.items() if task not in registered}
        report.check("beat 引用的任务已注册", not missing, f"未注册={missing}")

    # 路由支持通配（fnmatch），命中即视为已路由；未命中会静默落到默认队列。
    unrouted = sorted(
        name
        for name in registered
        if not any(fnmatch.fnmatchcase(name, pattern) for pattern in routes)
    )
    if unrouted:
        report.warn(
            "以下任务未显式路由，将落到默认队列", f"default={default_queue} tasks={unrouted}"
        )

    declarations = _task_declarations(backend_dir)
    names: dict[str, list[str]] = {}
    for path, func, explicit in declarations:
        if explicit:
            names.setdefault(explicit, []).append(f"{path.relative_to(backend_dir)}::{func}")
    duplicated = {name: where for name, where in names.items() if len(where) > 1}
    report.check("Celery 任务显式名不重复", not duplicated, f"重复={duplicated}")

    # autodiscover_tasks() 只扫描各 app 的 tasks.py。定义在别处的任务若未被显式导入，
    # 就不会出现在注册表里——.delay() 会在运行时报 "not registered"。
    unreachable: list[str] = []
    for path, func, explicit in declarations:
        if path.name == "tasks.py":
            continue
        expected = explicit or f"{_module_name(path, backend_dir)}.{func}"
        if expected not in registered:
            unreachable.append(f"{path.relative_to(backend_dir)}::{func} (期望名 {expected})")
    report.check(
        "tasks.py 之外的任务都必须已注册（需要显式导入）",
        not unreachable,
        f"未注册={unreachable}",
    )

    side_effect: list[str] = []
    for name in sorted(registered):
        module = getattr(type(celery_app.tasks[name]), "__module__", "")
        source = getattr(sys.modules.get(module), "__file__", None)
        if source and Path(source).name != "tasks.py":
            side_effect.append(f"{name} <- {module}")
    if side_effect:
        report.warn("任务定义不在 tasks.py，注册依赖导入副作用", f"{side_effect}")

    print("       —— 任务注册表 ——")
    for name in sorted(registered):
        print(f"       {name}")


def check_deploy_queues(report: Report, root: Path) -> None:
    from django.conf import settings

    declared = {queue.name for queue in getattr(settings, "CELERY_TASK_QUEUES", ())}

    for relative in COMPOSE_FILES:
        path = root / relative
        if not path.is_file():
            report.warn(f"{relative} 不存在，跳过 -Q 校验")
            continue
        values = QUEUE_FLAG_RE.findall(path.read_text(encoding="utf-8"))
        if not values:
            report.check(
                f"{relative} 的 worker 声明 -Q",
                False,
                "未找到 -Q：worker 只会消费默认队列，其余队列的任务无人执行",
            )
            continue
        for value in values:
            actual = {item.strip() for item in value.split(",") if item.strip()}
            report.check(
                f"{relative} 的 -Q 与 CELERY_TASK_QUEUES 一致",
                actual == declared,
                f"-Q={sorted(actual)} declared={sorted(declared)}",
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="后端契约校验（只读）")
    parser.add_argument(
        "--settings",
        default=os.environ.get("DJANGO_SETTINGS_MODULE", DEFAULT_SETTINGS),
        help=f"Django 设置模块，默认 {DEFAULT_SETTINGS}",
    )
    parser.add_argument(
        "--backend-dir",
        default=str(Path(__file__).resolve().parent.parent / "backend"),
        help="backend 目录，默认取脚本同级的 backend/",
    )
    args = parser.parse_args(argv)

    backend_dir = Path(args.backend_dir).resolve()
    if not (backend_dir / "manage.py").is_file():
        print(f"ERROR: {backend_dir} 下找不到 manage.py")
        return 2

    sys.path.insert(0, str(backend_dir))
    os.environ["DJANGO_SETTINGS_MODULE"] = args.settings

    import django

    django.setup()

    report = Report()
    sections = (
        ("路由契约", lambda: check_routes(report)),
        ("错误码契约", lambda: check_error_codes(report)),
        ("模型契约", lambda: check_models(report)),
        ("迁移红线", lambda: check_no_migrations(report, backend_dir)),
        ("Celery 契约", lambda: check_celery(report, backend_dir)),
        ("部署件一致性", lambda: check_deploy_queues(report, backend_dir.parent)),
    )
    for title, run in sections:
        print(f"\n=== {title} ===")
        run()

    print()
    if report.failures:
        print(f"FAILED: {len(report.failures)} 项未通过")
        for name in report.failures:
            print(f"  - {name}")
        return 1
    if report.warnings:
        print(f"ALL PASS（{len(report.warnings)} 项提示）")
    else:
        print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
