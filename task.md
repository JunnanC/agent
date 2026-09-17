# common 模块 Task

## 实施范围

本任务仅实现 `apps.common` 横切能力与对应测试，不实现任何业务模块。所有数据库模型均使用非托管模型映射 V4.0 冻结表，不生成迁移、不修改表结构。

实施顺序遵循依赖关系：基础数据结构与错误处理 → 请求上下文与日志 → HTTP 横切能力 → 幂等 → Outbox → 审计 → API 集成 → 全量质量检查。

## 文件清单

### 新增源码文件

```text
agent/backend/apps/common/responses.py
agent/backend/apps/common/errors.py
agent/backend/apps/common/context.py
agent/backend/apps/common/middleware.py
agent/backend/apps/common/logging.py
agent/backend/apps/common/pagination.py
agent/backend/apps/common/idempotency.py
agent/backend/apps/common/models.py
agent/backend/apps/common/outbox.py
agent/backend/apps/common/outbox_transport.py
agent/backend/apps/common/audit.py
agent/backend/apps/common/audit_export.py
agent/backend/apps/common/permissions.py
agent/backend/apps/common/providers.py
agent/backend/apps/common/serializers.py
agent/backend/apps/common/views.py
agent/backend/apps/common/urls.py
```

### 新增测试文件

```text
agent/backend/apps/common/tests/__init__.py
agent/backend/apps/common/tests/test_responses.py
agent/backend/apps/common/tests/test_errors.py
agent/backend/apps/common/tests/test_context.py
agent/backend/apps/common/tests/test_logging.py
agent/backend/apps/common/tests/test_pagination.py
agent/backend/apps/common/tests/test_idempotency.py
agent/backend/apps/common/tests/test_outbox.py
agent/backend/apps/common/tests/test_audit.py
agent/backend/apps/common/tests/test_permissions.py
agent/backend/apps/common/tests/test_api.py
```

### 修改源码文件

```text
agent/backend/apps/common/constants.py
agent/backend/config/settings/base.py
agent/backend/config/settings/test.py
agent/backend/config/urls.py
agent/backend/pyproject.toml
```

### 文档文件

```text
agent/README.md
agent/backend/README.md
```

## 有序任务

### T1: 基础常量与响应信封

**涉及文件：**

```text
agent/backend/apps/common/constants.py
agent/backend/apps/common/responses.py
agent/backend/apps/common/tests/test_responses.py
```

**步骤：**

1. 补充分页、幂等、Outbox、审计与导出相关常量。
2. 实现成功、列表、异步 202、错误四类响应构造函数。
3. 保持成功 `code` 为整数 `0`，错误 `code` 为接口文档数字错误码。
4. 确保所有响应都包含 `request_id`。

**验证：**

```powershell
uv run pytest agent/backend/apps/common/tests/test_responses.py -q
```

**通过标准：**

- 四类响应结构与接口文档一致。
- 列表 `data` 只包含 `items`、`page`、`page_size`、`total`。
- 异步 202 包含 `operation_id`、`trace_id`、`status`。
- 成功 `code` 为 `0`，错误 `code` 为文档指定数字码。

### T2: 错误码字典与统一异常处理

**涉及文件：**

```text
agent/backend/apps/common/errors.py
agent/backend/apps/common/tests/test_errors.py
```

**步骤：**

1. 定义 `ErrorCode` 数据结构，包含数字码、符号名、HTTP 状态与默认消息。
2. 集中定义第 24.1、24.2 节通用错误码与业务补充错误码。
3. 实现统一异常与错误响应转换。
4. 实现 DRF 全局异常处理器，保证未知异常返回 `INTERNAL_ERROR`。
5. 以数字码作为对外协议，保留符号名作为内部常量别名与映射键。

**验证：**

```powershell
uv run pytest agent/backend/apps/common/tests/test_errors.py -q
```

**通过标准：**

- 错误码唯一。
- HTTP 映射逐条断言通过。
- 未知异常不暴露堆栈，返回统一错误信封。
- 业务模块只能通过导入该字典使用错误码。

### T3: 请求上下文与中间件

**涉及文件：**

```text
agent/backend/apps/common/context.py
agent/backend/apps/common/middleware.py
agent/backend/config/settings/base.py
agent/backend/apps/common/tests/test_context.py
```

**步骤：**

1. 使用 `contextvars` 实现 `RequestContext` 的设置、读取与清理。
2. 实现 `X-Request-ID` 透传与 UUIDv4 生成。
3. 实现 `X-Trace-ID` 透传与生成。
4. 将上下文写入响应头。
5. 在请求入口设置上下文，在响应后清理上下文。
6. 将中间件加入 Django `MIDDLEWARE`。
7. 记录请求开始时间、结束时间与耗时。

**验证：**

```powershell
uv run pytest agent/backend/apps/common/tests/test_context.py -q
uv run pytest agent/backend/apps/common/tests/test_api.py -q
```

**通过标准：**

- 请求无 `X-Request-ID` 时生成 UUIDv4。
- 请求携带合法 `X-Request-ID` 时透传。
- 响应头包含 `X-Request-ID`。
- 上下文在同步与异步请求中均可读取。
- 请求结束后上下文被清理。

### T4: 脱敏 JSON 日志

**涉及文件：**

```text
agent/backend/apps/common/logging.py
agent/backend/apps/common/middleware.py
agent/backend/apps/common/tests/test_logging.py
```

**步骤：**

1. 实现敏感键名识别与值掩码。
2. 实现字符串值中 Token、Cookie、Authorization、API Key 模式脱敏。
3. 实现递归脱敏字典与列表。
4. 实现 JSON 日志 formatter。
5. 实现统一日志出口函数，自动注入上下文与耗时。
6. 在中间件响应完成后输出访问日志。

**验证：**

```powershell
uv run pytest agent/backend/apps/common/tests/test_logging.py -q
```

**通过标准：**

- 日志为合法 JSON。
- 包含 `request_id`、`trace_id`、用户标识、动作、耗时。
- 不出现密码、Token、Cookie、Authorization 头、API 密钥明文。
- 嵌套结构同样完成脱敏。

### T5: 统一分页器

**涉及文件：**

```text
agent/backend/apps/common/pagination.py
agent/backend/apps/common/tests/test_pagination.py
```

**步骤：**

1. 实现 `PageParams` 与 `PageResult`。
2. 实现请求参数解析与校验。
3. 实现 `page_size` 默认 20、最大 100、超限截断。
4. 实现 `page` 最小 1 校验。
5. 实现 `order` 白名单 `asc`/`desc`。
6. 实现 `sort` 白名单校验。
7. 分页前追加唯一 ID 作为稳定排序兜底。
8. 实现 queryset 分页与总数计算。

**验证：**

```powershell
uv run pytest agent/backend/apps/common/tests/test_pagination.py -q
```

**通过标准：**

- 非法排序字段被拒绝。
- `page_size` 超限截断为 100。
- 翻页无重复、无丢失。
- 默认排序稳定。
- 输出结构符合列表响应信封。

### T6: 抽象契约与权限基类

**涉及文件：**

```text
agent/backend/apps/common/providers.py
agent/backend/apps/common/permissions.py
agent/backend/config/settings/base.py
agent/backend/apps/common/tests/test_permissions.py
```

**步骤：**

1. 定义 `PermissionDecision`。
2. 定义 `PrincipalPermissionProvider` 与 `AuditableActorProvider` Protocol。
3. 通过 settings 字符串路径实现延迟加载。
4. 实现基础角色矩阵：USER、ORG_SUB_ADMIN、ORG_ADMIN、SYSTEM_ADMIN。
5. 实现 `/me/*`、`/teaching/*`、`/admin/*` 三类接口域的基础判断。
6. 保持 common 不导入任何业务模块。

**验证：**

```powershell
uv run pytest agent/backend/apps/common/tests/test_permissions.py -q
rg -n "from apps\.(?!common)|import apps\.(?!common)" agent/backend/apps/common
```

**通过标准：**

- 角色矩阵与规范一致。
- Provider 通过字符串路径加载。
- Provider 加载失败返回内部错误。
- common 源码不导入业务模块。

### T7: Redis 幂等能力

**涉及文件：**

```text
agent/backend/apps/common/idempotency.py
agent/backend/config/settings/base.py
agent/backend/apps/common/tests/test_idempotency.py
```

**步骤：**

1. 定义幂等 key 格式：用户标识 + 接口范围 + `Idempotency-Key`。
2. 实现请求摘要计算，覆盖方法、范围、路径、查询与请求体。
3. 实现请求 key UUID 格式校验。
4. 实现 Lua 脚本原子创建 `PENDING` 记录。
5. 实现同摘要完成态回放原 HTTP 状态码与响应体。
6. 实现同摘要进行态等待与回放。
7. 实现不同摘要 409 `IDEMPOTENCY_CONFLICT`。
8. 实现执行后回填 `COMPLETED`、状态码与响应体。
9. 设置 TTL 至少 24 小时。
10. 实现可选装饰器，仅启用于指定写操作。

**验证：**

```powershell
uv run pytest agent/backend/apps/common/tests/test_idempotency.py -q
```

**通过标准：**

- 同 key 并发两次只执行一次业务。
- 第二次返回首次状态码与响应体。
- 不同摘要返回 409。
- TTL 失效后可重新执行。
- GET、HEAD、OPTIONS 不要求 key。
- 失败响应也会被记录并回放。

### T8: 非托管模型

**涉及文件：**

```text
agent/backend/apps/common/models.py
agent/backend/apps/common/tests/test_outbox.py
agent/backend/apps/common/tests/test_audit.py
```

**步骤：**

1. 定义 `OutboxEvent` 非托管模型，严格映射 16 列。
2. 定义 `AuditLog` 非托管模型，严格映射 19 列。
3. 不生成迁移。
4. 不实现 update/delete 业务封装。
5. 为测试显式说明模型字段与冻结表列一一对应。

**验证：**

```powershell
uv run pytest agent/backend/apps/common/tests/test_outbox.py agent/backend/apps/common/tests/test_audit.py -q
```

**通过标准：**

- `managed=False`。
- 表名分别为 `outbox_events`、`audit_logs`。
- 字段数量、名称、可空性与 V4.0 冻结结构一致。
- 仓库不新增 migration 文件。

### T9: Outbox 事务发布与投递

**涉及文件：**

```text
agent/backend/apps/common/outbox.py
agent/backend/apps/common/outbox_transport.py
agent/backend/apps/common/tests/test_outbox.py
```

**步骤：**

1. 定义 `OutboxMessage` 与 `OutboxTransport`。
2. 实现 `publish_outbox`，只允许在当前数据库事务中调用。
3. 生成 UUIDv4 事件 ID 与 UTC `occurred_at`。
4. 组装最小载荷字段与可选关联 ID。
5. 对载荷与错误信息统一脱敏。
6. 将记录插入 `outbox_events`，与业务事实同事务提交。
7. 实现到期事件批量领取与行级条件更新。
8. 实现 Redis Streams 默认传输。
9. 实现成功、失败、指数退避与最多 10 次后置 `DEAD`。
10. 实现后台投递任务入口。

**验证：**

```powershell
uv run pytest agent/backend/apps/common/tests/test_outbox.py -q
```

**通过标准：**

- 非事务调用直接失败。
- 业务回滚时 Outbox 插入一起回滚。
- 事件载荷包含 `event_id`、`event_type`、`occurred_at`、`trace_id`。
- 多实例领取不重复。
- 成功后状态为 `PUBLISHED`。
- 失败尝试计数正确。
- 第 10 次失败后状态为 `DEAD`。
- 投递器不包含业务事件消费逻辑。

### T10: 统一审计记录

**涉及文件：**

```text
agent/backend/apps/common/audit.py
agent/backend/apps/common/logging.py
agent/backend/apps/common/tests/test_audit.py
```

**步骤：**

1. 定义 `AuditRecord` 输入结构。
2. 实现统一 `record_audit`。
3. 使用当前 `request_id`、`trace_id`、用户与动作。
4. 生成 UTC `occurred_at` 与 `created_at`。
5. 对 IP 执行统一脱敏。
6. 对用户代理计算摘要，不保存原文。
7. 对 reason、before、after、payload 统一脱敏。
8. 只执行 INSERT，不提供 UPDATE/DELETE 封装。
9. 确认 SUCCESS、DENIED、FAILURE 都会落审计。

**验证：**

```powershell
uv run pytest agent/backend/apps/common/tests/test_audit.py -q
```

**通过标准：**

- 三种结果均插入审计行。
- 系统动作 actor user 可为空。
- IP 与 JSON 字段完成脱敏。
- 用户代理只保存摘要。
- 数据库触发器阻止 UPDATE/DELETE。
- 字段总数与冻结表一致。

### T11: 审计检索 API

**涉及文件：**

```text
agent/backend/apps/common/serializers.py
agent/backend/apps/common/views.py
agent/backend/apps/common/urls.py
agent/backend/apps/common/tests/test_api.py
```

**步骤：**

1. 实现审计检索参数序列化与校验。
2. 支持用户、动作、目标、请求、追踪、关联资源、IP 与时间范围筛选。
3. 支持分页与排序白名单。
4. 关联 assignment ID 与 instance ID 查询。
5. 默认 `created_at` 倒序，唯一 ID 作为稳定排序。
6. 仅允许 `SYSTEM_ADMIN` 访问。
7. 返回统一列表信封。

**验证：**

```powershell
uv run pytest agent/backend/apps/common/tests/test_api.py -q
```

**通过标准：**

- 多条件筛选命中正确。
- 关联查询返回全部相关日志。
- 非法排序字段被拒绝。
- 非 SYSTEM_ADMIN 返回 FORBIDDEN。
- 响应为统一列表信封。

### T12: 审计异步导出

**涉及文件：**

```text
agent/backend/apps/common/audit_export.py
agent/backend/apps/common/views.py
agent/backend/apps/common/tests/test_api.py
```

**步骤：**

1. 实现导出参数校验：filters、format、mask_fields。
2. 空筛选返回 40004 对应验证错误。
3. 单次超过 100,000 条返回 42205 对应错误。
4. 生成 operation ID 与 trace ID。
5. 返回 202 异步受理信封。
6. 使用 Celery 异步执行导出。
7. 使用流式 CSV/JSON 生成器控制内存。
8. 默认脱敏 `ip_address` 与 `user_agent`。
9. 上传至 MinIO export bucket。
10. 生成 24 小时 `expires_at`。
11. 在 Redis 保存 operation 状态与完成态元数据。
12. 幂等回放同一导出请求。
13. 导出动作写入 `audit_logs`。

**验证：**

```powershell
uv run pytest agent/backend/apps/common/tests/test_api.py -q
```

**通过标准：**

- 空筛选返回指定错误。
- 超上限返回指定错误。
- 202 响应包含 operation ID、trace ID 与状态。
- CSV 与 JSON 文件内容正确。
- 文件落入 export bucket。
- `expires_at` 为 24 小时。
- 导出动作落审计。
- 同 key 重复请求回放首次结果。

### T13: API 与配置集成

**涉及文件：**

```text
agent/backend/config/settings/base.py
agent/backend/config/settings/test.py
agent/backend/config/urls.py
agent/backend/apps/common/views.py
agent/backend/apps/common/urls.py
```

**步骤：**

1. 注册 request/trace 中间件。
2. 注册 DRF 异常处理器。
3. 添加 Provider 字符串路径配置。
4. 添加幂等 TTL、Outbox 批量、审计导出限制配置。
5. 挂载 common 路由。
6. 确认健康检查仍正常。
7. 保证测试环境不依赖外部服务。

**验证：**

```powershell
uv run pytest agent/backend/apps/common -q
uv run python agent/backend/manage.py check --settings=config.settings.test
```

**通过标准：**

- 路由可解析。
- 中间件顺序正确。
- 配置缺失时错误清晰。
- Django check 无错误。
- 全部 common 测试通过。

### T14: 文档更新

**涉及文件：**

```text
agent/README.md
agent/backend/README.md
```

**步骤：**

1. 说明 common 能力清单。
2. 说明响应信封与错误码引用方式。
3. 说明幂等装饰器使用方式。
4. 说明 Outbox 发布函数使用方式。
5. 说明统一审计记录方式。
6. 说明配置项与默认值。
7. 标注数据库表为 V4.0 非托管映射，不生成迁移。

**验证：**

```powershell
rg -n "common|幂等|Outbox|审计|request_id" agent/README.md agent/backend/README.md
```

**通过标准：**

- 文档覆盖全部对外能力。
- 不描述业务模块实现。
- 明确 common 与业务模块的依赖边界。

### T15: 质量与覆盖率

**涉及文件：**

```text
agent/backend/pyproject.toml
agent/backend/apps/common/**
```

**步骤：**

1. 配置 pytest 与覆盖率统计。
2. 运行格式化检查。
3. 运行静态检查。
4. 运行全量测试。
5. 输出覆盖率报告。
6. 检查 common 无业务模块导入。
7. 检查源码无明文密钥模式。

**验证命令：**

```powershell
Set-Location agent
uv run ruff format --check backend
uv run ruff check backend
uv run pytest backend/apps/common -q --cov=apps.common --cov-report=term-missing
rg -n "from apps\.(?!common)|import apps\.(?!common)" backend/apps/common
rg -n "(password|token|cookie|authorization|api[_-]?key).{0,20}(=|:).{0,20}(?!<masked>|\\*\\*\\*)" backend/apps/common
```

**通过标准：**

- `ruff format --check` 通过。
- `ruff check` 通过。
- 全量 common 测试通过。
- 覆盖率不低于 80%。
- common 不导入业务模块。
- 静态扫描未发现密钥明文。

## 里程碑

| 里程碑 | 包含任务 | 出口条件 |
|---|---|---|
| M0 基础能力 | T1~T5 | 响应、错误、上下文、日志、分页测试通过 |
| M1 鉴权与幂等 | T6~T7 | Provider 与幂等测试通过 |
| M2 数据集成 | T8~T10 | 非托管模型、Outbox、审计测试通过 |
| M3 API 能力 | T11~T13 | 审计检索、导出、配置集成测试通过 |
| M4 交付 | T14~T15 | 文档、覆盖率、格式与静态检查全部通过 |

## 外部依赖

- MySQL 8.0：Outbox 与审计模型集成测试。
- Redis 7 db 0：幂等、导出状态与 Redis Streams 传输测试。
- Redis 7 db 1：Celery broker/result，保持逻辑库隔离。
- MinIO export bucket：审计导出文件测试。

单元测试必须能在无外部服务环境运行；数据库、Redis、MinIO 相关行为使用集成测试标记，可按需执行。

## 明确不做的任务

- 不新增或修改任何业务模块。
- 不新增数据库表或 migration。
- 不实现业务事件消费。
- 不代行业务表级幂等约束。
- 不实现身份认证与用户资料。
- 不以符号码作为对外错误协议。
