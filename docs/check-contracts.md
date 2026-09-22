# 后端契约校验脚本使用说明

## 1. 脚本定位

`scripts/check-contracts.py` 是一个只读校验脚本，用于把后端结构约定固化为可执行检查。它不会修改任何文件，只读取代码和配置并输出检查结果。

适用对象：

- 后端开发：提交前自查结构契约。
- 测试人员：复核路由、错误码、模型、迁移、Celery 和部署件是否满足约定。
- 运维人员：确认 worker 队列声明与 compose 配置一致。
- CI：可作为后续静态检查或部署前检查命令接入。

## 2. 检查范围

脚本覆盖以下契约：

1. **路由契约**
   - 路由路径不重复。
   - 路由形状不互相遮蔽，例如 `<int:id>` 与 `<str:id>` 视为同一形状。
   - 打印完整路由登记表，便于 diff 和评审。

2. **错误码契约**
   - 必须存在集中定义的 `ErrorCode` 与 `ERROR_CODES`。
   - 错误码数值必须唯一。
   - 常量名必须与 `ErrorCode.symbol` 一致。
   - 所有已定义的 `ErrorCode` 都必须登记进 `ERROR_CODES`。

3. **模型契约**
   - 业务模型必须全部 `managed = False`。
   - `db_table` 不得冲突。

4. **迁移红线**
   - `backend/apps/*/migrations/` 下不得存在迁移文件。
   - 该约定用于避免冻结库阶段误执行 `makemigrations`。

5. **Celery 契约**
   - `CELERY_TASK_QUEUES` 必须非空，且包含默认队列。
   - 任务路由目标队列必须已声明。
   - `CELERY_BEAT_SCHEDULE` 必须非空。
   - beat 引用的任务必须已注册。
   - 显式任务名不得重复。
   - `tasks.py` 之外定义的任务必须已注册。

6. **部署件一致性**
   - `docker-compose.yml` 中 worker 的 `-Q` 必须与其 `CELERY_TASK_QUEUES` 一致。
   - `docker-compose.prod.yml` 中 worker 的 `-Q` 必须与其 `CELERY_TASK_QUEUES` 一致。
   - 两个文件中的队列集合还必须与 Django settings 中的 `CELERY_TASK_QUEUES` 一致。

## 3. 运行方式

### 3.1 从仓库根目录运行

```bash
python scripts/check-contracts.py
```

默认后端目录为 `backend`。

### 3.2 从 `backend` 目录运行

```bash
python ../scripts/check-contracts.py
```

脚本会自动识别当前目录下是否存在 `manage.py`。

### 3.3 显式指定后端目录和 settings

```bash
python scripts/check-contracts.py \
  --backend-dir backend \
  --settings config.settings.test
```

Windows PowerShell 示例：

```powershell
python scripts/check-contracts.py `
  --backend-dir backend `
  --settings config.settings.test
```

## 4. 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--backend-dir` | 自动识别 `backend` | 指定后端目录，目录下必须存在 `manage.py`。 |
| `--settings` | `config.settings.test` | 指定 Django settings 模块。 |

## 5. 输出结果解读

脚本输出包含以下三类状态：

- `PASS`：该项契约通过。
- `WARN`：存在提示性漂移，但不阻断。
- `FAIL`：存在必须修复的契约漂移。

示例：

```text
[PASS] 路径不重复 | 9 条路由
[WARN] 业务模型存在 | 当前 apps 下没有业务模型
[FAIL] beat 非空（否则 Outbox 永不投递） | entries=[]
```

## 6. 退出码

| 退出码 | 含义 |
|---|---|
| `0` | 所有必须通过的契约均通过，`WARN` 不影响结果。 |
| `1` | 存在 `FAIL`，需要处理后重新执行。 |
| `2` | 脚本参数或后端目录不正确，未进入契约检查。 |

测试人员和运维人员应以退出码作为最终判断依据。

## 7. 当前已知基线

截至 2026-09-21，当前仓库运行结果为：

```text
PASS=14
WARN=1
FAIL=0
```

当前仅有 1 项 `WARN`：

`apps.identity.tasks.import_users` 未显式路由，将落到默认队列 `celery`。该提示不阻断退出码。

## 8. 注意事项

- 脚本只读，不会修改任何文件。
- 不需要连接 MySQL。
- 不需要启动 Redis、Celery worker 或 Django 服务。
- 如果本地缺少依赖，请先在 `backend` 目录执行依赖安装。
