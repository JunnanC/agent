# teaching 模块 · 教师端写侧地基设计（v1.0 草案）

本文件是「教师端 幂等 / Audit / Outbox 及事务服务」的设计基线，同时作为本模块的使用约定。
状态：**范围已确认（2026-09-22）**。按 §4 实施，按 §6 验收。

## 0. 结论摘要

今天在 `apps/teaching` 落「写侧地基」，**不改 `apps/common`，不新建幂等/审计/Outbox 表**：

| 能力 | 今天的做法 |
|---|---|
| 幂等 | 复用 `apps.common.idempotency.idempotent`，教师端只维护 **scope 注册表**（`idempotency.py`） |
| Audit | 复用 `apps.common.audit`，教师端提供 `audit_teaching()` 薄封装（`services/audit.py`） |
| Outbox | 复用 `apps.common.outbox`，教师端提供 `publish_teaching_event()` 薄封装（`services/outbox.py`） |
| 事务服务 | `services/writes.py` 的 `teaching_write()`：保证「业务事实 + 审计 + Outbox」同事务 |
| 准入 | `permissions.py`：教学端 = `TEACHING` portal + 角色矩阵 |
| 路由 | **今天不挂路由**（理由见 D2） |

## 1. 基线与既有事实

### 1.1 团队冻结文档依据

设计依据为 `documents/Guideline/01-10`（v1.0）。该目录随 `8eb97b3` 进入历史，后按仓库 `.gitignore` 的 `/documents/` 规则停止跟踪，**当前不在 master 树内**，需从历史提交取用。

| 依据 | 内容 |
|---|---|
| 03 §1.4 | 数据库事务只覆盖本地事实状态、Outbox 和审计，不等待运行时操作完成 |
| 03 §1.6 | 关系数据库是业务事实来源；Redis 只承担缓存、短期状态、锁、限流和队列，不保存唯一事实 |
| 03 §5 | API 事务：业务状态 + Outbox + 审计 → Celery → SSE → compensation_jobs；Outbox 消费者按 `event_id` 去重 |
| 04 §2 | `outbox_events`、`audit_logs` 是冻结表 |
| 04 §4 | 必须落实的事务：同一事务内提交「业务事实 + 审计 + 通知 Outbox」 |
| 04 §7 | 禁止原地覆盖事件或审计日志；禁止把 Redis 当唯一事实来源 |
| 05 §1 | 幂等键适用于所有改变事实或触发外部动作的接口；服务端至少保留 24 小时；重放返回原状态码与响应体；键与请求摘要不一致返回 `IDEMPOTENCY_CONFLICT` |
| 05 §3 | 教学端接口清单（前缀 `/api/v1`） |
| 05 §6 | 错误码字典 |
| 07 §2 | M1 = 工程基础与身份授权（含幂等/审计/Outbox 基础，以及教师审核/直接添加/移除）；M2 = 模板、预检与教学任务；M8 = 教学/系统管理前端 |

### 1.2 master 已有的实现（不得重复实现）

| 能力 | 位置 | 现状 |
|---|---|---|
| 幂等 | `apps/common/idempotency.py` | Redis 占位、结果重放、摘要冲突 `40902`、并发 `PENDING` 等待 |
| 审计 | `apps/common/audit.py`、`apps/common/models.py` | `AuditRecord`、`record_audit`、IP 掩码、UA 哈希、递归脱敏 |
| Outbox | `apps/common/outbox.py`、`apps/common/models.py` | `OutboxMessage`、`publish_outbox`（**强制在事务内**，否则抛 `INTERNAL_ERROR`） |
| 派发 | `apps/common/tasks.py`、`CELERY_BEAT_SCHEDULE` | `apps.common.dispatch_outbox` 每 10s，路由到 `maintenance` 队列 |
| 门户 | `apps/common/portal/*` | `PortalContextMiddleware` 写 `request.portal`（USER / TEACHING / PLATFORM） |
| 角色 | `apps/common/permissions.py` | `ROLE_MATRIX`、`require_route_permission(request, "teaching")` |
| actor | `apps/common/providers.py` | `actor_identifier` / `actor_role`，走 `COMMON_AUDITABLE_ACTOR_PROVIDER` |
| 事务服务样板 | `apps/membership/services.py` | 现有的 `transaction.atomic()` + `record_audit` + `publish_outbox` 写法 |
| 契约门禁 | `scripts/check-contracts.py` | 路由 / 错误码 / 模型 / 迁移 / Celery / compose 六类检查 |

`apps/teaching` 当前只有 `__init__.py` 与 `apps.py`（`TeachingConfig` + `label = "teaching"`），已进 `INSTALLED_APPS`；无 models、无 urls、未接入 `config/urls.py`。

## 2. 范围与非目标

**今天交付**：`apps/teaching` 的常量、准入、审计/Outbox 域封装、事务服务编排、幂等 scope 注册表，以及本文件。

**不做**：

1. 不新建幂等 / `outbox_events` / `audit_logs` 表（见 D1）。
2. 不改 `apps/common` 任何文件。
3. 不实现模板、任务、审核、归档等 M2/M5 域模型（责任人不同，见 07 §2）。
4. 不新增 `/teaching/*` 路由（见 D2）。
5. 不提交测试代码与测试文档（团队分工：测试由测试同学入库）。

## 3. 关键设计决策

### D1 三张能力模型归属 common，教师端不重复建表

- **决策**：`outbox_events` / `audit_logs` 直接使用 `apps.common.models` 的模型；幂等继续用 common 的 Redis 实现。
- **理由（可验证）**：
  1. 冻结 schema（04 §2）中只有 `outbox_events` 与 `audit_logs`，**没有幂等表**；
  2. `scripts/check-contracts.py::check_models` 有「db_table 不冲突」硬门禁，教师端再建同名表会直接 FAIL；
  3. `backend/README.md` 明确 `apps/common` 是横切底座，业务模块不得重复实现同一能力。
- **被拒绝的方案**：在 `apps/teaching` 建教师端私有的三张能力表。语义与 common 重复，且需要先变更冻结 schema，属团队级决策，不在今天范围。

### D2 今天不挂路由

`apps/membership` 已占用 `/teaching/team-members`、`/teaching/team-membership-applications/*`；`check-contracts.py::check_routes` 会检查「路径不重复」与「路径形状不互相遮蔽」。M2 的教学端切片（模板/任务）路径尚未冻结，今天新增路由必然撞车。因此今天只交付可被 import 的服务层，路由由第一个真正使用它的切片挂载。

### D3 事务服务用显式上下文管理器，不做隐式魔法

不使用 `Model.save()` 重写、不使用信号（`post_save`）、不使用基类自动埋点。统一入口是一个显式上下文：

```python
from apps.teaching.services.writes import teaching_write

with teaching_write(
    request=request,
    action=EVENT_TASK_PUBLISHED,
    target_type=AGGREGATE_TASK,
    target_id=task_id,
) as write:
    ...业务写入...
    write.after = {"status": "PUBLISHED"}
    write.publish(
        event_type=EVENT_TASK_PUBLISHED,
        aggregate_type=AGGREGATE_TASK,
        aggregate_id=task_id,
        topic=TOPIC_TEACHING_TASK,
        payload={"task_id": task_id},
    )
```

理由：Doc 03 §5 要求「业务状态 + Outbox + 审计」同事务，事务内的写入顺序与回滚语义必须一眼可读；隐式埋点容易在异常路径漏审计。

### D4 幂等占位先于数据库事务

`teaching_idempotent(scope)` 在视图层先占位（Redis），再进入 `transaction.atomic()`。并发重复请求应在进入事务前被拦住，避免两个请求都拿到行锁再互相等待。

### D5 拒绝类操作要留痕，业务类失败不回滚审计

对齐 `apps/membership/services.py` 的既有做法：

- **被拒绝/被阻断**（业务事实本就不成立）：在事务内只写审计（`result="DENIED"`）与必要的快照，**不写业务事实**；把要抛的 `ApiError` 缓存到变量，**退出事务后**再抛，保证审计已提交、不被回滚。
- **业务写入后失败**：整个事务回滚，业务事实、审计、Outbox 一起回滚（保持「审计与事实同事务」的强一致语义）。此路径不额外在独立事务里补写审计。

`teaching_write()` 对这两种路径都提供支持：`write.deny(error, reason=...)` 走前者，直接抛异常走后者。

### D6 「幂等标记」是否落库（待裁决）

04 §4 写「配额释放先写业务事实和幂等标记」。现状幂等只在 Redis（03 §1.6 允许 Redis 承担短期状态）。若教学端需要「可审计、可对账的幂等标记」，需要新增落库表，属冻结 schema 变更，须由 PM / 后端 1 裁决。今天按 Redis 现状实现，不落库。

## 4. 详细实施设计

### 4.1 文件清单

```text
backend/apps/teaching/
├── README.md                     新增，本设计 + 使用约定
├── constants.py                  新增，事件/聚合/topic/幂等 scope/审计动作常量
├── permissions.py                新增，TeachingPortalPermission + require_teaching_actor
├── idempotency.py                新增，scope 注册表 + teaching_idempotent(scope)
└── services/
    ├── __init__.py               新增，对外导出
    ├── audit.py                  新增，audit_teaching()
    ├── outbox.py                 新增，publish_teaching_event()
    └── writes.py                 新增，teaching_write() 事务编排
```

今天**不建 `models.py`**：教师端尚无自有表；`check-contracts.py::check_models` 只在 `apps/` 下完全没有业务模型时才 WARN，现有 common/membership/identity 已提供模型，不建空模块不会触发提示。

### 4.2 `constants.py` 命名约定

| 类别 | 约定 | 示例 |
|---|---|---|
| 事件类型 | `<domain>.<fact>` | `task.published`、`task.withdrawn`、`report.reviewed` |
| 聚合类型 | 大写下划线 | `TASK`、`REPORT_VERSION` |
| topic | `<domain>.<aggregate>.events` | `teaching.task.events`（与 membership 的 `membership.events` 并列） |
| 幂等 scope | `<domain>.<operation>` | `teaching.task.publish` |
| 审计动作 | 与事件类型同名，便于按动作检索 | `task.published` |

**约束**：scope 只能从 `constants.py` 取常量，禁止在视图里写字面量；`IDEMPOTENCY_SCOPES` 冻结集合用于校验「注册表与实际用值一致」。

### 4.3 `services/audit.py`

```python
def audit_teaching(
    request,
    *,
    action: str,
    target_type: str,
    target_id: str,
    result: str = "SUCCESS",
    reason: str = "",
    before=None,
    after=None,
    assignment_id: str | None = None,
    instance_id: str | None = None,
) -> None: ...
```

- actor 一律从 `actor_identifier(request)` / `actor_role(request)` 取，**不从请求体取**（05 §1：不信任客户端归属声明）。
- `trace_id` / `request_id` 从 `current_trace_id()` / `current_request_id()` 取。
- `idempotency_key` 从 `Idempotency-Key` 请求头取。
- `ip` 掩码、`user_agent` 哈希、`before/after` 递归脱敏全部交给 `apps.common.audit`，本模块不重复实现。
- **只能在事务内调用**（与业务事实同事务）。

### 4.4 `services/outbox.py`

```python
def publish_teaching_event(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    topic: str,
    payload: dict | None = None,
    assignment_id: str | None = None,
    instance_id: str | None = None,
): ...
```

- 在 `publish_outbox` 之上再加一层运行时断言：不在 `teaching_write()` 事务内调用时，报错信息直接指向本模块，便于定位。
- 载荷只放 opaque ID、状态与业务必要的非敏感字段；不放大对象正文与凭据（04 §6）。

### 4.5 `services/writes.py` 事务契约

```python
with teaching_write(request=..., action=..., target_type=..., target_id=...) as write:
    ...
```

| 阶段 | 行为 |
|---|---|
| 进入 | 开启 `transaction.atomic()`；捕获 actor、`trace_id`、`request_id` |
| 正常退出 | 写 `result="SUCCESS"` 审计 → 派发已登记的事件（同事务）→ 提交 |
| `write.deny(error, *, reason="")` | 只写 `result="DENIED"` 审计；事务提交后抛出 `error`（业务事实不落库） |
| 抛异常 | 整体回滚；不补写独立事务审计（见 D5） |

`write` 暴露：`after`（审计 after_json）、`publish(...)`（登记事件）、`deny(...)`。

### 4.6 `permissions.py`

```python
class TeachingPortalPermission(PortalPermission):
    required_portals = frozenset({TEACHING_PORTAL})


def require_teaching_actor(request) -> str: ...
```

- `require_teaching_actor` 先做 portal 校验，再走 `require_route_permission(request, "teaching")`（`ROLE_MATRIX`：`ORG_ADMIN` = ALL，`ORG_SUB_ADMIN` = AUTHORIZED，`USER` / `SYSTEM_ADMIN` = NONE），返回 `actor_user_id`。
- portal 只是额外边界，**不替代账号授权**（与 `PortalPermission` 的注释一致）。

### 4.7 时序

```text
Client ── POST (Idempotency-Key) ──▶ View
  │ @teaching_idempotent("teaching.task.publish")        # Redis 占位 / 重放，先于事务
  │ require_teaching_actor(request)                      # portal + 角色矩阵
  └─ teaching_write(...)                                 # BEGIN
       业务写入（M2 的 service）
       audit_teaching(result="SUCCESS")      ─┐
       publish_teaching_event(...)           ─┤ 同一事务
     COMMIT                                  ─┘
  └─ 响应写入 Redis（供重放）

Worker：dispatch_outbox（每 10s，maintenance 队列）→ 投递事件 → SSE
```

## 5. 与队友的边界（防撞车）

- 不动 `apps/common`、`config/settings/*`、`config/urls.py`。
- 不碰 `apps/membership` 的 `/teaching/*` 路由与 service。
- M2 / M5 后端调用本模块的 `teaching_write()` / `audit_teaching()` / `publish_teaching_event()`，**不自己再写一套** audit / outbox。
- 新增事件类型、聚合类型、幂等 scope 一律追加到 `constants.py`，并在 PR 描述里说明，避免各自起名。

## 6. 验收标准

### 6.1 命令级（全部必须通过）

```powershell
Set-Location agent\backend
.venv\Scripts\python.exe manage.py check --settings=config.settings.test
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
Set-Location ..
python scripts\check-contracts.py
```

1. `manage.py check` 无 issue；
2. `ruff check .` 全绿；`ruff format --check apps/teaching` 全绿（本切片全部文件已格式化）。注意：`ruff format --check .` 在 master 上对 15 个既有文件本来就为 red（非本切片引入，属队友文件），本地验证以切片目录为准（doc 06 §7.6 质量门禁）；
3. `pytest -q` 现有用例全部通过，无回归；
4. `scripts/check-contracts.py` 六类检查全部 PASS，`FAIL=0`：路由不重复 / 不遮蔽、错误码唯一、业务模型全 `managed=False`、`apps/*/migrations/` 无迁移文件、Celery 队列与任务路由一致、compose 队列一致。

### 6.2 行为级（本地临时用例，验证后删除，不入库）

1. 未配置 actor provider 时 `teaching_write` **fail-closed**，不静默放行；
2. 正常路径：事务提交后 `outbox_events` 与 `audit_logs` 各多一行，`trace_id` / `request_id` 与请求一致；
3. `write.deny()`：业务事实不入库，审计以 `DENIED` 落库，接口返回对应 `ApiError` 状态码；
4. 业务写入抛异常：整事务回滚，`outbox_events` 无新增；
5. Outbox 行 `status` 允许被 `dispatch_outbox` 派发；
6. 审计中 `ip` 已掩码、`user_agent` 只存哈希、`before/after` 中 `password` / `token` 类字段已脱敏；
7. 幂等：同键同摘要重放返回原状态码与原响应体；同键不同摘要返回 `IDEMPOTENCY_CONFLICT`（40902）。

### 6.3 出口条件

- PR 不含测试代码与测试文档；
- 不新增迁移文件（`apps/*/migrations/` 为空）；
- 与 master 无路由、接口、db_table 冲突；
- 本 README 的 §7 问题全部有结论。

## 7. 已确认的范围决策（2026-09-22）

| # | 问题 | 结论 |
|---|---|---|
| Q1 | 本次交付范围 | **只交付地基**，不带真实端点。真实端点属 M2 教学端切片，本次加会与 M2 撞车 |
| Q2 | 04 §4 的「幂等标记」是否落库 | **不落库**，保持 Redis 实现；D6 的落库方案留作后续独立变更 |
| Q3 | 「教师端」的口径 | 指**教学端 portal（`TEACHING`）**，不是 membership 已有的 `/teaching/*` 接口集合 |
| Q4 | 本切片归属 | 记 **M1 延伸**（写侧基础能力）；M8 教学/管理前端在其后 |

范围确认后，§2「非目标」与 §6.3「出口条件」即为本次出口判据。
