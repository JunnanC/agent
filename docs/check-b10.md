# B10 专项验收脚本使用说明

## 1. 脚本定位

`scripts/check_b10.py` 是一个只读的 B10 专项验收脚本，用于把「对象资产与失败补偿模型」切片的结构契约固化为可执行检查。它不会修改任何文件，只读取 Django 模型元数据和源码目录并输出检查结果。

适用对象：

- 后端开发：提交 B10 相关改动前自查模型契约。
- 测试人员：复核 B10 四个模型、索引、枚举和 AppendOnly 不变量。
- 评审人员：确认实现没有越界到 serializer、迁移、执行器或基础设施调用。

与 `scripts/check-contracts.py` 的关系：

- `check-contracts.py` 面向全项目结构契约，例如路由、错误码、Celery 和部署件。
- `check_b10.py` 面向 B10 切片专项验收，只检查本切片新增的数据模型与本地不变量。
- B10 合入前建议同时运行两个脚本；日常 B10 迭代可优先运行专项脚本。

## 2. 检查范围

脚本覆盖以下 B10 契约：

1. **模型元数据**
   - `ObjectAsset` 必须存在，表名为 `core_object_asset`。
   - `FailureRecord` 必须存在，表名为 `core_failure_record`。
   - `CompensationTask` 必须存在，表名为 `core_compensation_task`。
   - `ObjectPurgeLog` 必须存在，表名为 `core_object_purge_log`。
   - 四个模型必须全部 `managed = False`，模型 label 必须为 `core.*`。

2. **字段契约**
   - 按照切片 DDL 逐项校验字段名、顺序、类型、默认值、长度、排序规则、可空性、主键和唯一约束。
   - `ObjectPurgeLog.asset` 必须映射到 `asset_id`，并使用 `ON DELETE RESTRICT`。
   - `ObjectAsset.owner_course_id` 必须是普通 `BigIntegerField`，不得建立跨层 ForeignKey。

3. **索引与唯一约束**
   - `ObjectAsset` 必须包含四个二级索引：
     `(owner_user_id, purpose, status)`、`(owner_course_id, purpose)`、`(status, retention_until)`、`(scan_status, created_at)`。
   - `FailureRecord` 必须包含 `(resource_type, resource_public_id, id)`、`(failure_code, created_at)`、`(trace_id)` 三个索引。
   - `CompensationTask` 必须包含 `(status, next_run_at)`、`(target_type, target_public_id)` 两个索引。
   - `ObjectPurgeLog` 必须包含 `(asset, id)` 索引。
   - `ObjectAsset` 必须包含 `(bucket, object_key)` 唯一约束。

4. **枚举契约**
   - `ObjectAsset.purpose` 必须为六个 DDL 定义值。
   - `ObjectAsset.scan_status` 必须为 `PENDING / CLEAN / INFECTED / FAILED`。
   - `ObjectAsset.status` 必须为 `ACTIVE / PURGED`。
   - `CompensationTask.status` 必须为 `PENDING / RUNNING / SUCCEEDED / DEAD`。
   - `ObjectPurgeLog.operator_type` 必须为 `SYSTEM / ADMIN`。
   - `apps.runtime.enums.CompensationStatus` 必须包含 `DEAD`，core 不得另建并行补偿状态枚举。

5. **AppendOnly 不变量**
   - `FailureRecord` 与 `ObjectPurgeLog` 不得包含 `updated_at`、`row_version`。
   - 已存在的 `FailureRecord.save()` 必须被模型层拒绝。
   - 已存在的 `ObjectPurgeLog.save()` 必须被模型层拒绝。
   - `FailureRecord.delete()` 必须被模型层拒绝。
   - `ObjectPurgeLog.delete()` 必须被模型层拒绝。
   - 防护异常必须复用 `apps.core.append_only.AppendOnlyViolation`。

6. **Versioned 不变量**
   - `ObjectAsset.row_version` 默认值必须为 `1`。
   - `CompensationTask.row_version` 默认值必须为 `1`。

7. **范围红线**
   - `backend/apps/core/migrations/` 只能包含 `__init__.py`，不得生成迁移文件。
   - B10 不创建 core serializer。
   - `bucket`、`object_key` 不得出现在任何 `serializers.py` 中。
   - 脚本自身只导入模型，不发起查询，不连接 MySQL、Redis、MinIO 或 ClamAV。

8. **OPEN 提示**
   - 输出 B10 相关 OPEN 事项，包括 `OPEN-DB-07`、`OPEN-B10-01`、`OPEN-B10-02`、`OPEN-B10-03`、`OPEN-B10-04`、`OPEN-B10-06`。
   - OPEN 输出为 `INFO`，不会影响退出码。

## 3. 运行方式

### 3.1 从仓库根目录运行

```bash
python scripts/check_b10.py
```

默认后端目录为 `backend`。

### 3.2 从 `backend` 目录运行

```bash
python ../scripts/check_b10.py
```

脚本会自动识别当前目录下是否存在 `manage.py`。

### 3.3 显式指定后端目录和 settings

```bash
python scripts/check_b10.py \
  --backend-dir backend \
  --settings config.settings.test
```

Windows PowerShell 示例：

```powershell
python scripts/check_b10.py `
  --backend-dir backend `
  --settings config.settings.test
```

## 4. 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--backend-dir` | 自动识别 `backend` | 指定后端目录，目录下必须存在 `manage.py`。 |
| `--settings` | `config.settings.test` | 指定 Django settings 模块。 |

## 5. 输出结果解读

脚本输出包含以下状态：

- `PASS`：该项 B10 契约通过。
- `FAIL`：存在必须修复的 B10 契约漂移。
- `INFO`：说明性信息，例如只读验证方式和 OPEN 清单，不影响退出码。

示例：

```text
[PASS] B10 模型元数据 | core.ObjectAsset: table=core_object_asset, managed=False
[PASS] B10 字段契约 | ObjectAsset: 17 个字段逐项对齐
[FAIL] B10 枚举契约 | CompensationTask.status: ['PENDING', 'RUNNING', 'FAILED']; expected=['PENDING', 'RUNNING', 'SUCCEEDED', 'DEAD']
[INFO] OPEN-B10-03 | PENDING -> DEAD transition remains unspecified
```

## 6. 退出码

| 退出码 | 含义 |
|---|---|
| `0` | 所有 B10 必须通过的契约均通过。 |
| `1` | 存在 `FAIL`，需要处理后重新执行。 |

测试人员和评审人员应以退出码作为最终判断依据。

## 7. 当前已知基线

截至 2026-09-28，当前仓库运行结果为：

```text
PASS=30
FAIL=0
B10 ALL PASS
```

当前脚本会输出以下 OPEN 提示：

- `OPEN-DB-07`：BigAutoField signed 与 DDL BIGINT UNSIGNED 的差异仍需 V00 决策。
- `OPEN-B10-01`：`owner_user_id` 的 ForeignKey 延迟到 `accounts_user` 模型落地后处理。
- `OPEN-B10-02`：AppendOnly 防护层级需与 B8 测试工厂写入方式统一。
- `OPEN-B10-03`：`PENDING -> DEAD` 是否允许直接跃迁仍待裁决。
- `OPEN-B10-04`：对象清理执行器与补偿调度器的切片归属待指派。
- `OPEN-B10-06`：既有 `outbox_events` 与 `audit_logs` 表名差异需项目经理裁决。

## 8. 注意事项

- 脚本只读，不会修改任何文件。
- 不需要连接 MySQL。
- 不需要启动 Redis、Celery worker 或 Django 服务。
- 不执行 `migrate`，不生成迁移文件。
- 脚本只做 B10 专项验收，不能替代 `scripts/check-contracts.py` 的全项目契约检查。
- 如果本地缺少依赖，请先在 `backend` 目录执行依赖安装。
