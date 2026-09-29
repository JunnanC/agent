#!/usr/bin/env python
"""B10 object asset and compensation model acceptance checks.

This is a focused, read-only acceptance script for slice B10.  It intentionally
does not replace scripts/check-contracts.py and does not perform broad project
contract checks.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

    def info(self, name: str, detail: str = "") -> None:
        self.add("INFO", name, detail)

    def fail(self, name: str, detail: str = "") -> None:
        self.add("FAIL", name, detail)

    @property
    def failed(self) -> int:
        return sum(result.status == "FAIL" for result in self.results)


MODEL_TABLES = {
    "ObjectAsset": "core_object_asset",
    "FailureRecord": "core_failure_record",
    "CompensationTask": "core_compensation_task",
    "ObjectPurgeLog": "core_object_purge_log",
}

FIELD_SPECS: dict[str, dict[str, dict[str, Any]]] = {
    "ObjectAsset": {
        "id": {"type": "BigAutoField", "primary_key": True},
        "public_id": {
            "type": "CharField",
            "max_length": 26,
            "unique": True,
            "collation": "ascii_bin",
        },
        "bucket": {"type": "CharField", "max_length": 128},
        "object_key": {"type": "CharField", "max_length": 512},
        "byte_size": {"type": "PositiveBigIntegerField"},
        "content_type": {"type": "CharField", "max_length": 128},
        "sha256_digest": {
            "type": "CharField",
            "max_length": 64,
            "collation": "ascii_bin",
        },
        "owner_user_id": {"type": "BigIntegerField"},
        "owner_course_id": {"type": "BigIntegerField", "null": True},
        "purpose": {"type": "CharField", "max_length": 32},
        "scan_status": {"type": "CharField", "max_length": 16, "default": "PENDING"},
        "scanned_at": {"type": "DateTimeField", "null": True},
        "retention_until": {"type": "DateTimeField", "null": True},
        "status": {"type": "CharField", "max_length": 16, "default": "ACTIVE"},
        "created_at": {"type": "DateTimeField"},
        "updated_at": {"type": "DateTimeField"},
        "row_version": {"type": "PositiveIntegerField", "default": 1},
    },
    "FailureRecord": {
        "id": {"type": "BigAutoField", "primary_key": True},
        "failure_code": {"type": "CharField", "max_length": 64},
        "stage": {"type": "CharField", "max_length": 32, "null": True},
        "resource_type": {"type": "CharField", "max_length": 64},
        "resource_public_id": {
            "type": "CharField",
            "max_length": 26,
            "collation": "ascii_bin",
        },
        "previous_status": {"type": "CharField", "max_length": 32, "null": True},
        "retryable": {"type": "BooleanField", "default": False},
        "detail_masked": {"type": "CharField", "max_length": 512, "null": True},
        "trace_id": {"type": "CharField", "max_length": 32, "collation": "ascii_bin"},
        "created_at": {"type": "DateTimeField"},
    },
    "CompensationTask": {
        "id": {"type": "BigAutoField", "primary_key": True},
        "public_id": {
            "type": "CharField",
            "max_length": 26,
            "unique": True,
            "collation": "ascii_bin",
        },
        "compensation_type": {"type": "CharField", "max_length": 64},
        "target_type": {"type": "CharField", "max_length": 64},
        "target_public_id": {
            "type": "CharField",
            "max_length": 26,
            "collation": "ascii_bin",
        },
        "status": {"type": "CharField", "max_length": 16, "default": "PENDING"},
        "attempt_count": {"type": "PositiveIntegerField", "default": 0},
        "next_run_at": {"type": "DateTimeField", "null": True},
        "last_error_masked": {"type": "CharField", "max_length": 512, "null": True},
        "created_at": {"type": "DateTimeField"},
        "updated_at": {"type": "DateTimeField"},
        "row_version": {"type": "PositiveIntegerField", "default": 1},
    },
    "ObjectPurgeLog": {
        "id": {"type": "BigAutoField", "primary_key": True},
        "asset": {"type": "ForeignKey", "column": "asset_id", "on_delete": "RESTRICT"},
        "purge_reason": {"type": "CharField", "max_length": 64},
        "reference_check_json": {"type": "JSONField", "null": True},
        "object_removed_at": {"type": "DateTimeField", "null": True},
        "operator_type": {"type": "CharField", "max_length": 16},
        "created_at": {"type": "DateTimeField"},
    },
}

EXPECTED_INDEXES = {
    "ObjectAsset": [
        ("owner_user_id", "purpose", "status"),
        ("owner_course_id", "purpose"),
        ("status", "retention_until"),
        ("scan_status", "created_at"),
    ],
    "FailureRecord": [
        ("resource_type", "resource_public_id", "id"),
        ("failure_code", "created_at"),
        ("trace_id",),
    ],
    "CompensationTask": [
        ("status", "next_run_at"),
        ("target_type", "target_public_id"),
    ],
    "ObjectPurgeLog": [("asset", "id")],
}

EXPECTED_CHOICES = {
    ("ObjectAsset", "purpose"): [
        "REPORT_ATTACHMENT",
        "WORKSPACE_SNAPSHOT",
        "ARCHIVE_PACKAGE",
        "AGENT_TRANSCRIPT",
        "TEMPLATE_MATERIAL",
        "IDENTITY_DOCUMENT",
    ],
    ("ObjectAsset", "scan_status"): ["PENDING", "CLEAN", "INFECTED", "FAILED"],
    ("ObjectAsset", "status"): ["ACTIVE", "PURGED"],
    ("CompensationTask", "status"): ["PENDING", "RUNNING", "SUCCEEDED", "DEAD"],
    ("ObjectPurgeLog", "operator_type"): ["SYSTEM", "ADMIN"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-dir", type=Path, default=DEFAULT_BACKEND_DIR)
    parser.add_argument("--settings", default=DEFAULT_SETTINGS)
    return parser.parse_args()


def setup_django(backend_dir: Path, settings: str) -> None:
    if not (backend_dir / "manage.py").is_file():
        raise SystemExit(f"backend directory does not contain manage.py: {backend_dir}")
    backend_str = str(backend_dir.resolve())
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)
    os.environ["DJANGO_SETTINGS_MODULE"] = settings
    import django

    django.setup()


def check_metadata(report: Report, models: dict[str, type]) -> None:
    for name, table in MODEL_TABLES.items():
        model = models[name]
        label = model._meta.label
        managed = model._meta.managed
        actual_table = model._meta.db_table
        if label != f"core.{name}" or actual_table != table or managed is not False:
            report.fail(
                "B10 模型元数据",
                f"{label}: table={actual_table}, managed={managed}; expected core.{name}: table={table}, managed=False",
            )
        else:
            report.pass_("B10 模型元数据", f"{label}: table={table}, managed=False")


def check_fields(report: Report, models: dict[str, type]) -> None:
    for model_name, specs in FIELD_SPECS.items():
        model = models[model_name]
        actual_names = [field.name for field in model._meta.fields]
        expected_names = list(specs)
        if actual_names != expected_names:
            report.fail(
                "B10 字段清单",
                f"{model_name}: fields={actual_names}; expected={expected_names}",
            )
            continue

        mismatches: list[str] = []
        for field_name, expected in specs.items():
            field = model._meta.get_field(field_name)
            actual = {
                "type": field.get_internal_type(),
                "primary_key": field.primary_key,
                "max_length": getattr(field, "max_length", None),
                "unique": field.unique,
                "null": field.null,
                "collation": getattr(field, "db_collation", None),
                "default": field.get_default(),
                "column": field.column,
                "on_delete": (
                    getattr(getattr(field, "remote_field", None), "on_delete", None)
                    and field.remote_field.on_delete.__name__
                ),
            }
            for key, value in expected.items():
                if actual.get(key) != value:
                    mismatches.append(
                        f"{model_name}.{field_name}.{key}={actual.get(key)!r}"
                    )
        if mismatches:
            report.fail("B10 字段契约", "; ".join(mismatches))
        else:
            report.pass_("B10 字段契约", f"{model_name}: {len(specs)} 个字段逐项对齐")


def check_indexes(report: Report, models: dict[str, type]) -> None:
    for model_name, expected in EXPECTED_INDEXES.items():
        model = models[model_name]
        actual = [tuple(index.fields) for index in model._meta.indexes]
        if sorted(actual) != sorted(expected):
            report.fail("B10 索引契约", f"{model_name}: {actual}; expected={expected}")
        else:
            report.pass_("B10 索引契约", f"{model_name}: {len(expected)} 个二级索引")

    asset = models["ObjectAsset"]
    unique_constraints = {
        tuple(constraint.fields)
        for constraint in asset._meta.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    if unique_constraints != {("bucket", "object_key")}:
        report.fail("B10 唯一约束", f"constraints={unique_constraints}")
    else:
        report.pass_("B10 唯一约束", "public_id unique + (bucket, object_key) unique")


def check_choices(report: Report, models: dict[str, type]) -> None:
    for (model_name, field_name), expected in EXPECTED_CHOICES.items():
        field = models[model_name]._meta.get_field(field_name)
        actual = [value for value, _label in field.choices]
        if actual != expected:
            report.fail(
                "B10 枚举契约",
                f"{model_name}.{field_name}: {actual}; expected={expected}",
            )
        else:
            report.pass_("B10 枚举契约", f"{model_name}.{field_name}: {actual}")

    from apps.runtime.enums import CompensationStatus

    if CompensationStatus.DEAD.value != "DEAD":
        report.fail("runtime 补偿枚举", "CompensationStatus.DEAD is missing")
    else:
        report.pass_(
            "runtime 补偿枚举", "CompensationStatus.DEAD=DEAD; core 复用 runtime 枚举"
        )


def check_invariants(report: Report, models: dict[str, type]) -> None:
    from apps.core.append_only import AppendOnlyViolation

    for model_name in ("FailureRecord", "ObjectPurgeLog"):
        model = models[model_name]
        field_names = {field.name for field in model._meta.fields}
        polluted = field_names.intersection({"updated_at", "row_version"})
        if polluted:
            report.fail(
                "AppendOnly 无污染", f"{model_name}: unexpected fields={polluted}"
            )
        else:
            report.pass_(
                "AppendOnly 无污染", f"{model_name}: no updated_at/row_version"
            )

    failure = models["FailureRecord"](
        failure_code="CHECK",
        resource_type="CHECK",
        resource_public_id="0" * 26,
        trace_id="0" * 32,
        created_at="2026-01-01T00:00:00Z",
    )
    failure.pk = 1
    try:
        failure.save()
    except AppendOnlyViolation:
        report.pass_("AppendOnly 防更新", "FailureRecord.save() rejected")
    else:
        report.fail("AppendOnly 防更新", "FailureRecord.save() was not rejected")

    try:
        failure.delete()
    except AppendOnlyViolation:
        report.pass_("AppendOnly 防删除", "FailureRecord.delete() rejected")
    else:
        report.fail("AppendOnly 防删除", "FailureRecord.delete() was not rejected")

    asset = models["ObjectAsset"](
        public_id="0" * 26,
        bucket="check",
        object_key="check",
        byte_size=1,
        content_type="application/octet-stream",
        sha256_digest="0" * 64,
        owner_user_id=1,
        purpose="REPORT_ATTACHMENT",
        created_at="2026-01-01T00:00:00Z",
    )
    purge_log = models["ObjectPurgeLog"](
        asset=asset,
        purge_reason="CHECK",
        operator_type="SYSTEM",
        created_at="2026-01-01T00:00:00Z",
    )
    purge_log.pk = 1
    try:
        purge_log.save()
    except AppendOnlyViolation:
        report.pass_("AppendOnly 防更新", "ObjectPurgeLog.save() rejected")
    else:
        report.fail("AppendOnly 防更新", "ObjectPurgeLog.save() was not rejected")

    try:
        purge_log.delete()
    except AppendOnlyViolation:
        report.pass_("AppendOnly 防删除", "ObjectPurgeLog.delete() rejected")
    else:
        report.fail("AppendOnly 防删除", "ObjectPurgeLog.delete() was not rejected")

    if asset.row_version != 1:
        report.fail(
            "Versioned 默认版本", f"ObjectAsset.row_version={asset.row_version}"
        )
    else:
        report.pass_("Versioned 默认版本", "ObjectAsset.row_version=1")

    task = models["CompensationTask"](
        public_id="0" * 26,
        compensation_type="CHECK",
        target_type="CHECK",
        target_public_id="0" * 26,
        created_at="2026-01-01T00:00:00Z",
    )
    if task.row_version != 1:
        report.fail(
            "Versioned 默认版本", f"CompensationTask.row_version={task.row_version}"
        )
    else:
        report.pass_("Versioned 默认版本", "CompensationTask.row_version=1")

    owner_course_field = models["ObjectAsset"]._meta.get_field("owner_course_id")
    if owner_course_field.get_internal_type() != "BigIntegerField":
        report.fail(
            "跨层引用", f"owner_course_id type={owner_course_field.get_internal_type()}"
        )
    else:
        report.pass_("跨层引用", "owner_course_id is BigIntegerField; no ForeignKey")


def check_scope(report: Report, backend_dir: Path) -> None:
    migrations_dir = backend_dir / "apps" / "core" / "migrations"
    migration_files = [
        path.name
        for path in migrations_dir.iterdir()
        if path.is_file() and path.suffix == ".py" and path.name != "__init__.py"
    ]
    if migration_files:
        report.fail("迁移红线", f"unexpected migrations={migration_files}")
    else:
        report.pass_("迁移红线", "apps/core/migrations contains only __init__.py")

    serializer_paths = list((backend_dir / "apps").rglob("serializers.py"))
    leaked = [
        str(path.relative_to(backend_dir))
        for path in serializer_paths
        if "bucket" in path.read_text(encoding="utf-8")
        or "object_key" in path.read_text(encoding="utf-8")
    ]
    core_serializer = backend_dir / "apps" / "core" / "serializers.py"
    if core_serializer.exists() or leaked:
        report.fail(
            "对象元数据不外泄",
            f"core serializer exists={core_serializer.exists()}; leaked={leaked}",
        )
    else:
        report.pass_(
            "对象元数据不外泄",
            "B10 未创建 serializer；bucket/object_key 未出现在 serializers.py",
        )

    report.info(
        "只读验收",
        "script imports models only; no query, migrate, MySQL, Redis, MinIO, or ClamAV call",
    )
    report.info(
        "OPEN-DB-07", "BigAutoField signed vs DDL BIGINT UNSIGNED remains for V00 gate"
    )
    report.info(
        "OPEN-B10-01", "owner_user_id FK deferred until accounts_user model exists"
    )
    report.info(
        "OPEN-B10-02", "AppendOnly protection layer placement to align with B8 factory"
    )
    report.info("OPEN-B10-03", "PENDING -> DEAD transition remains unspecified")
    report.info(
        "OPEN-B10-04", "purge executor and compensation scheduler slice ownership"
    )
    report.info(
        "OPEN-B10-06",
        "legacy outbox_events/audit_logs table naming remains for PM decision",
    )


def main() -> int:
    args = parse_args()
    print("=== B10 专项验收 ===")
    print(f"backend={args.backend_dir.resolve()}")
    print(f"settings={args.settings}")
    setup_django(args.backend_dir, args.settings)

    from apps.core import models as core_models

    models = {name: getattr(core_models, name) for name in MODEL_TABLES}
    report = Report()
    check_metadata(report, models)
    check_fields(report, models)
    check_indexes(report, models)
    check_choices(report, models)
    check_invariants(report, models)
    check_scope(report, args.backend_dir)

    passed = sum(result.status == "PASS" for result in report.results)
    failed = report.failed
    print("\n=== B10 汇总 ===")
    print(f"PASS={passed}")
    print(f"FAIL={failed}")
    print("B10 ALL PASS" if failed == 0 else "B10 FAILED")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
