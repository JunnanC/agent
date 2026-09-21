# M1-membership 任务拆解 Task

## 任务顺序

### T1 应用骨架与常量

**涉及文件：**

```text
agent/backend/apps/membership/__init__.py
agent/backend/apps/membership/apps.py
agent/backend/apps/membership/constants.py
agent/backend/pyproject.toml
agent/backend/config/settings/base.py
```

**步骤：**

1. 创建 `apps.membership` 应用。
2. 集中定义成员状态、来源、事件类型、状态转移、阻断类型。
3. 保留 C8/C9/C11/C12/C13 保守策略及 `# CONFLICT-*` 注释位置说明。
4. 将应用加入 `INSTALLED_APPS` 与打包配置。

**验证：**

```powershell
Set-Location agent
uv run python backend/manage.py check --settings=config.settings.test
```

### T2 非托管模型

**涉及文件：**

```text
agent/backend/apps/membership/models.py
agent/backend/apps/membership/tests/test_models.py
```

**步骤：**

1. 按 V4.0 映射 `team_settings` 19 列。
2. 按 V4.0 映射 `team_memberships` 18 列与索引名。
3. 设置 `managed = False`，不生成 migration。
4. 验证默认表名、字段名、`db_column` 与数据库快照一致。

**验证：**

```powershell
Set-Location agent
uv run pytest backend/apps/membership/tests/test_models.py -q
```

### T3 状态机与领域服务

**涉及文件：**

```text
agent/backend/apps/membership/services.py
agent/backend/apps/membership/tests/test_state_machine.py
agent/backend/apps/membership/tests/test_services.py
```

**步骤：**

1. 实现显式状态转移函数与非法转移拦截。
2. 实现实时 ACTIVE 判定、活动成员 ID 获取与 ACTIVE 断言。
3. 实现 `previous_status` 记录和 `update_fields` 精确更新。
4. 实现团队设置读取。
5. 覆盖 `None/REJECTED/EXITED/REMOVED -> PENDING`、审核转移、退出/移除转移。

**验证：**

```powershell
Set-Location agent
uv run pytest backend/apps/membership/tests/test_state_machine.py backend/apps/membership/tests/test_services.py -q
```

### T4 阻断检查接缝

**涉及文件：**

```text
agent/backend/apps/membership/blocking.py
agent/backend/apps/membership/tests/test_blocking.py
```

**步骤：**

1. 定义 `BlockItem` 数据结构。
2. 实现退出阻断范围：`ASSIGNED` 至 `UNDER_REVIEW`。
3. 实现移除阻断范围：`PROVISIONING/RUNNING/SUBMITTED`。
4. 通过可替换只读 adapter 获取其他模块事实，不直接写他人表。
5. 将阻断清单写入 `last_block_check_json`。

**验证：**

```powershell
Set-Location agent
uv run pytest backend/apps/membership/tests/test_blocking.py -q
```

### T5 用户端 API

**涉及文件：**

```text
agent/backend/apps/membership/serializers.py
agent/backend/apps/membership/selectors.py
agent/backend/apps/membership/views.py
agent/backend/apps/membership/urls.py
agent/backend/apps/membership/tests/test_me_api.py
```

**步骤：**

1. 实现当前用户成员记录查询，强制只读自身数据。
2. 实现申请与重新申请。
3. 实现主动退出。
4. 使用统一响应信封、`data.items` 分页、幂等装饰器、审计与 Outbox。
5. 校验角色、字段长度、状态过滤与 `blocking_summary`。

**验证：**

```powershell
Set-Location agent
uv run pytest backend/apps/membership/tests/test_me_api.py -q
```

### T6 教学端 API

**涉及文件：**

```text
agent/backend/apps/membership/serializers.py
agent/backend/apps/membership/selectors.py
agent/backend/apps/membership/views.py
agent/backend/apps/membership/urls.py
agent/backend/apps/membership/tests/test_teaching_api.py
```

**步骤：**

1. 实现成员分页列表、状态多选、关键词搜索与摘要。
2. 实现待审核申请列表与已拒绝申请追溯。
3. 实现审核 APPROVE/REJECT。
4. 实现直接添加成员。
5. 实现移除成员与最后管理员保护。
6. 脱敏手机号与邮箱；服务层独立校验角色与范围。

**验证：**

```powershell
Set-Location agent
uv run pytest backend/apps/membership/tests/test_teaching_api.py -q
```

### T7 identity 接缝

**涉及文件：**

```text
agent/backend/apps/membership/identity_provider.py
agent/backend/config/settings/base.py
agent/backend/apps/identity/tests/**
agent/backend/apps/membership/tests/test_identity_provider.py
```

**步骤：**

1. 实现 `get_membership`，确保返回 `membership_id` 与 `status` 或 `None`。
2. 实现 `unverified_start_policy`，返回 `DENIED/READ_ONLY/ALLOWED`。
3. 实现 `revoke_authentication_sessions`，仅发布会话撤销 Outbox 事件。
4. 将 `IDENTITY_MEMBERSHIP_PROVIDER` 指向新实现。
5. 运行 identity 全量回归测试。

**验证：**

```powershell
Set-Location agent
uv run pytest backend/apps/identity -q
uv run pytest backend/apps/membership/tests/test_identity_provider.py -q
```

### T8 并发与幂等测试

**涉及文件：**

```text
agent/backend/apps/membership/tests/test_concurrency.py
agent/backend/apps/membership/tests/test_idempotency.py
```

**步骤：**

1. 覆盖重复申请与唯一约束。
2. 覆盖审核并发，仅一次成功。
3. 覆盖退出/移除与阻断检查事务。
4. 覆盖最后管理员并发保护。
5. 覆盖同一幂等键重放原响应、不同摘要冲突。

**验证：**

```powershell
Set-Location agent
uv run pytest backend/apps/membership/tests/test_concurrency.py backend/apps/membership/tests/test_idempotency.py -q
```

### T9 事件、审计与安全测试

**涉及文件：**

```text
agent/backend/apps/membership/tests/test_events.py
agent/backend/apps/membership/tests/test_audit.py
agent/backend/apps/membership/tests/test_security.py
```

**步骤：**

1. 验证申请、审核、添加、退出、移除事件恰好发布一次。
2. 验证会话撤销事件 payload 不含凭据。
3. 验证审计包含 request/trace ID 与业务对象 ID。
4. 验证 USER/ORG_SUB_ADMIN/ORG_ADMIN 越权边界。
5. 验证手机号与邮箱脱敏，日志无明文凭据。

**验证：**

```powershell
Set-Location agent
uv run pytest backend/apps/membership/tests/test_events.py backend/apps/membership/tests/test_audit.py backend/apps/membership/tests/test_security.py -q
```

### T10 文档更新

**涉及文件：**

```text
agent/backend/apps/membership/README.md
agent/README.md
```

**步骤：**

1. 说明模块边界、状态机、接口、领域服务与接缝。
2. 说明幂等、审计、Outbox 与并发策略。
3. 说明阻断 adapter 与 C8/C9/C11/C12/C13 保守决策。
4. 补充运行、测试与回滚说明。

**验证：**

```powershell
Set-Location agent
rg -n "状态机|幂等|Outbox|审计|IDENTITY_MEMBERSHIP_PROVIDER|CONFLICT-" backend/apps/membership/README.md README.md
```

### T11 质量门禁

**涉及文件：**

```text
agent/backend/apps/membership/**
agent/backend/pyproject.toml
```

**步骤：**

1. 更新 pytest 路径与 coverage source。
2. 运行格式检查、静态检查、membership 全量测试。
3. 运行 identity 全量回归。
4. 输出覆盖率报告并确认不低于 80%。
5. 检查不新增表、migration、三方依赖和自造错误码。

**验证：**

```powershell
Set-Location agent
uv run ruff format --check backend
uv run ruff check backend
uv run pytest backend/apps/membership -q --cov=apps.membership --cov-report=term-missing
uv run pytest backend/apps/identity -q
uv run python backend/manage.py check --settings=config.settings.test
```

## 里程碑

| 里程碑 | 任务 | 出口条件 |
| --- | --- | --- |
| M0 骨架 | T1~T2 | 应用注册、模型映射与 check 通过 |
| M1 领域 | T3~T4 | 状态机、领域服务、阻断检查测试通过 |
| M2 API | T5~T6 | 用户端与教学端契约测试通过 |
| M3 接缝 | T7 | identity 回归通过 |
| M4 质量 | T8~T11 | 并发、幂等、安全、覆盖率与静态检查通过 |

## 明确不做

- 不生成 migration。
- 不修改数据库 DDL。
- 不直接读写其他模块业务表。
- 不实现 M4-B 消费者。
- 不新增三方依赖或错误码。
- 不修改前端。
