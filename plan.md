# common 模块 Plan

## 架构概览

common 作为 `apps.common` Django 应用实现，位于业务应用之前，只提供横切能力，不导入任何业务应用。所有持久化模型均为非托管模型，直接映射 V4.0 已冻结的 `outbox_events` 与 `audit_logs` 表，不生成迁移、不修改表结构。通用幂等与异步导出状态存放在 Redis db 0，与 Celery broker/result 的 db 1 隔离。

整体分为五层：

1. **HTTP 横切层**：统一响应、异常处理、request_id/trace_id 中间件、结构化日志、分页解析、幂等装饰器与权限基类。
2. **领域无关基础层**：错误码字典、响应信封、上下文存取、敏感信息脱敏、时间工具与 UUID 工具。
3. **事务性集成层**：Outbox 模型、事务内发布函数、投递器与传输抽象。
4. **审计层**：审计模型、统一记录函数、管理员检索 API、异步导出任务与对象存储写入。
5. **扩展契约层**：身份与权限提供者接口，通过 settings 字符串路径延迟加载，由 identity 后续实现。

模块依赖方向固定为：HTTP 横切层与业务视图 → 基础层 → 数据库/Redis/对象存储/抽象契约。common 不依赖任何业务模块，也不包含业务事件消费逻辑。

## 核心数据结构

### Envelope

统一响应使用显式构造函数，不通过共享父类隐式包装。

```python
def success(data: object, request_id: str) -> dict[str, object]
def paginated(items: list[object], page: int, page_size: int, total: int, request_id: str) -> dict[str, object]
def accepted(operation_id: str, trace_id: str, request_id: str, status: str = "ACCEPTED") -> dict[str, object]
def failure(code: int, message: str, request_id: str, details: list[dict[str, str]] | None = None) -> dict[str, object]
```

- 成功 `code` 固定为整数 `0`。
- 错误 `code` 固定为接口文档指定的整数数字码。
- 四类响应都必须返回 `request_id`。
- 列表响应的 `data` 只包含 `items`、`page`、`page_size`、`total`。

### ErrorCode

```python
@dataclass(frozen=True)
class ErrorCode:
    code: int
    symbol: str
    http_status: int
    message: str

def error_response(error: ErrorCode, request_id: str, details=None, message: str | None = None) -> JsonResponse
```

- `code` 为第 10、15 章示例中的数字错误码，是对外协议。
- `symbol` 保存第 24 章符号名，仅作为内部常量别名与映射键。
- 字典集中定义通用错误码与业务接口补充错误码。
- 业务模块只能从 `apps.common.errors` 引用错误码，禁止自造字符串。

### RequestContext

```python
@dataclass(frozen=True)
class RequestContext:
    request_id: str
    trace_id: str
    user_id: str | None
    action: str
```

- 基于 `contextvars` 实现协程安全的请求上下文。
- 提供读取函数：当前请求标识、追踪标识、用户标识与动作。
- 中间件负责进入请求时设置、响应后清理。
- Celery 任务与异步导出任务通过任务参数恢复上下文。

### PageParams 与 PageResult

```python
@dataclass(frozen=True)
class PageParams:
    page: int = 1
    page_size: int = 20
    sort: str | None = None
    order: Literal["asc", "desc"] = "desc"

@dataclass(frozen=True)
class PageResult:
    items: list[object]
    page: int
    page_size: int
    total: int
```

```python
def parse_page_params(request, allowed_sorts: set[str], default_sort: str) -> PageParams
def paginate_queryset(queryset, params: PageParams, default_sort: str) -> PageResult
```

- `page` 最小为 1。
- `page_size` 最小为 1、默认 20、最大 100，超限截断到 100。
- `sort` 不在白名单时返回 `VALIDATION_ERROR`。
- `order` 只允许 `asc` / `desc`。
- 分页前追加唯一标识列作为稳定排序兜底，避免翻页重复或丢失。

### IdempotencyRecord

Redis 记录使用 JSON 值，键格式为：

```text
idempotency:{user_id}:{scope}:{idempotency_key}
```

字段结构：

```json
{
  "request_digest": "sha256",
  "state": "PENDING|COMPLETED",
  "http_status": 200,
  "response_body": "{\"code\":0,...}"
}
```

- TTL 不低于 24 小时，从记录创建时开始计算。
- `PENDING` 与 `COMPLETED` 均保留 TTL。
- 摘要使用请求方法、接口范围、路径参数、查询参数与请求体计算。
- 回放时必须原样返回首次状态码与响应体。
- 摘要不一致返回 409 与 `IDEMPOTENCY_CONFLICT`。

### OutboxEvent

非托管 Django 模型，映射 `outbox_events` 16 列：

```python
class OutboxEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    event_id = models.CharField(max_length=36, unique=True)
    event_type = models.CharField(max_length=64)
    aggregate_type = models.CharField(max_length=64)
    aggregate_id = models.CharField(max_length=64)
    assignment_id = models.CharField(max_length=64, null=True, blank=True)
    instance_id = models.CharField(max_length=64, null=True, blank=True)
    topic = models.CharField(max_length=128)
    payload_json = models.JSONField()
    status = models.CharField(max_length=16)
    attempt_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField()
    published_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    trace_id = models.CharField(max_length=128)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "outbox_events"
```

说明：

- 字段名与冻结数据库契约保持一致；`assignment_id`、`instance_id` 仅作为不透明关联标识透传，common 不解释其业务含义。
- 状态只允许 `PENDING`、`PUBLISHED`、`FAILED`、`DEAD`。
- 尝试次数最大 10。
- 不提供更新 `created_at` 或事件标识的路径。

### OutboxMessage

```python
@dataclass(frozen=True)
class OutboxMessage:
    event_id: str
    event_type: str
    occurred_at: datetime
    trace_id: str
    aggregate_type: str
    aggregate_id: str
    topic: str
    assignment_id: str | None = None
    instance_id: str | None = None
    operation_id: str | None = None
    extra_payload: dict[str, object] | None = None
```

- `event_id` 由发布函数生成 UUIDv4。
- `occurred_at` 由发布函数统一生成为 UTC。
- 载荷写入前统一脱敏。
- `extra_payload` 仅允许通用 JSON 值，不定义业务语义。

### OutboxTransport

```python
class OutboxTransport(Protocol):
    def publish(self, topic: str, event_id: str, payload_json: str) -> None: ...
```

- 默认实现使用 Redis Streams，向 broker 逻辑库发布。
- 传输层只感知 topic、事件 ID 与序列化载荷，不感知任何业务事件。
- 后续可替换为独立消息中间件实现，无需修改发布函数与业务调用方。

### AuditRecord

统一审计输入结构：

```python
@dataclass(frozen=True)
class AuditRecord:
    actor_user_id: str | None
    actor_role_code: str | None
    action: str
    target_type: str
    target_id: str
    assignment_id: str | None = None
    instance_id: str | None = None
    trace_id: str
    request_id: str
    idempotency_key: str | None
    result: Literal["SUCCESS", "DENIED", "FAILURE"]
    reason: str
    before_json: object | None
    after_json: object | None
    ip: str
    user_agent_hash: str | None
```

- `occurred_at` 与 `created_at` 由统一记录函数生成 UTC 时间。
- `ip` 在进入函数前先执行 IPv4/IPv6 通用脱敏。
- `user_agent_hash` 只保存摘要，不保存用户代理原文。
- `before_json`、`after_json`、`reason` 写入前统一脱敏。
- 数据库契约中的关联字段仍使用冻结列名，common 不解释业务含义。

### AuditLog

非托管 Django 模型，映射 `audit_logs` 19 列：

```python
class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    actor_user_id = models.CharField(max_length=64, null=True, blank=True)
    actor_role_code = models.CharField(max_length=32, null=True, blank=True)
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=32)
    target_id = models.CharField(max_length=64)
    assignment_id = models.CharField(max_length=64, null=True, blank=True)
    instance_id = models.CharField(max_length=64, null=True, blank=True)
    trace_id = models.CharField(max_length=128)
    request_id = models.CharField(max_length=36)
    idempotency_key = models.CharField(max_length=64, null=True, blank=True)
    result = models.CharField(max_length=8)
    reason = models.TextField(blank=True, default="")
    before_json = models.JSONField(null=True)
    after_json = models.JSONField(null=True)
    ip = models.CharField(max_length=64, blank=True, default="")
    user_agent_hash = models.CharField(max_length=64, null=True, blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "audit_logs"
```

- 不提供更新或删除方法的封装。
- 数据库触发器负责强制仅追加语义，测试直接证明 UPDATE/DELETE 抛出 `AUDIT_LOG_APPEND_ONLY`。

### PermissionDecision

```python
@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    scope: Literal["SELF", "AUTHORIZED", "ALL", "NONE"]
    object_ids: set[str] | None = None
```

- `SELF` 表示本人范围。
- `AUTHORIZED` 表示授权范围，可附带对象 ID 集合。
- `ALL` 表示教学域全量范围。
- `NONE` 表示无权限。

### Provider 契约

```python
class PrincipalPermissionProvider(Protocol):
    def get_permission(self, actor_user_id: str, action: str) -> PermissionDecision: ...

class AuditableActorProvider(Protocol):
    def get_actor(self, request: HttpRequest) -> tuple[str | None, str | None]: ...
```

- 两个契约均由 identity 模块实现。
- common 通过 `django.utils.module_loading.import_string` 延迟加载。
- settings 使用字符串路径配置，避免编译期导入业务模块。
- 加载失败时返回 `INTERNAL_ERROR`，不在 common 内实现身份认证。

## 模块设计

### responses 模块

**职责：** 构造成功、列表、异步受理与错误响应信封。

**对外接口：** `success`、`paginated`、`accepted`、`failure`。

**依赖：** `errors`、`context`。

### errors 模块

**职责：** 集中维护数字错误码、符号名、HTTP 状态、默认消息与异常转换。

**对外接口：** 错误码常量、`ErrorCode` 字典、异常处理器、错误响应构造函数。

**依赖：** `responses`。

### context 模块

**职责：** 保存并读取当前请求的 `request_id`、`trace_id`、用户标识与动作。

**对外接口：** `RequestContext`、`set_context`、`clear_context`、`current_context`、单独字段读取函数。

**依赖：** 标准库 `contextvars`。

### middleware 模块

**职责：**

- 从 `X-Request-ID` 透传或生成 UUIDv4。
- 从 `X-Trace-ID` 透传或生成追踪标识。
- 将标识写入响应头、上下文与日志。
- 记录请求开始时间、结束时间与耗时。
- 请求异常时交给统一异常处理输出错误信封。

**依赖：** `context`、`responses`、`errors`、`logging`。

### logging 模块

**职责：** JSON 结构化日志与敏感字段脱敏。

**对外接口：**

```python
def mask_sensitive(value: object) -> object
def json_log(action: str, **fields: object) -> None
```

**脱敏规则：**

- 敏感键名包括密码、令牌、Cookie、Authorization、API key 等常见变体。
- 字典键命中时值替换为固定掩码。
- 字符串值中出现的 `Bearer` 令牌、长 Token、Cookie、API Key 模式替换为掩码。
- 日志出口统一调用脱敏函数。

**依赖：** `context`、标准库 `logging` 与 `json`。

### pagination 模块

**职责：** 解析并校验分页参数，对查询集执行稳定分页。

**对外接口：** `PageParams`、`PageResult`、`parse_page_params`、`paginate_queryset`。

**依赖：** Django ORM。

### idempotency 模块

**职责：** 为写操作提供 Redis 幂等记录、并发互斥、响应回放与冲突检测。

**对外接口：**

```python
def idempotent(scope: str) -> Callable[[ViewFunc], ViewFunc]
```

**关键流程：**

1. 仅处理 `POST`、`PUT`、`PATCH`、`DELETE`。
2. 读取并校验 `Idempotency-Key` 必须为 UUID。
3. 通过 `AuditableActorProvider` 获取用户标识，匿名用户使用固定标识。
4. 计算请求摘要。
5. 使用 Lua 脚本原子创建 `PENDING` 记录。
6. 已存在且摘要一致时：若 `COMPLETED` 直接回放；若 `PENDING` 等待首次请求完成后再回放。
7. 已存在且摘要不一致时返回 409。
8. 首次请求执行视图，将响应状态码与响应体写回 Redis，并刷新 TTL。
9. 视图抛出异常时记录失败响应并继续抛出，由统一异常处理生成信封。

**依赖：** Redis、`errors`、`context`、抽象 Actor 契约。

### outbox 模块

**职责：** 在当前数据库事务内写入 Outbox 记录，并提供通用投递器。

**对外接口：**

```python
def publish_outbox(message: OutboxMessage, *, available_at: datetime | None = None) -> OutboxEvent
def dispatch_due_outbox(limit: int = 100) -> int
```

**关键决策：**

- `publish_outbox` 不创建新事务，只使用当前事务，确保业务回滚时同步回滚。
- 若调用时不存在活动事务，直接返回内部错误，避免产生非事务性事件。
- 投递器按 `PENDING`、`available_at <= now`、稳定排序批量获取。
- 投递成功后更新为 `PUBLISHED` 并写 `published_at`。
- 投递失败时增加尝试次数，按指数退避更新 `available_at`；达到 10 次后置为 `DEAD`。
- `last_error` 写入前脱敏。
- 投递器不判断事件类型，不消费任何事件。

**依赖：** Django ORM、Redis 传输抽象、`logging`。

### audit 模块

**职责：** 提供统一审计写入、审计检索与审计导出。

**对外接口：**

```python
def record_audit(record: AuditRecord) -> AuditLog
def build_audit_queryset(filters: AuditQueryFilters) -> QuerySet[AuditLog]
```

**检索能力：**

- 用户、动作、目标类型、目标 ID、请求标识、追踪标识。
- 关联 assignment ID、instance ID。
- 脱敏 IP、创建时间范围。
- 页码、页大小、白名单排序。
- 默认 `created_at` 倒序，并以唯一 ID 作为稳定排序兜底。

**导出能力：**

- 仅 `SYSTEM_ADMIN` 可访问。
- 支持 CSV 与 JSON。
- 支持指定脱敏字段，默认 `ip_address` 与 `user_agent`。
- 返回 202 异步受理信封。
- 单次最多 100,000 条，超出返回 `FILE_TOO_LARGE` 或第 24 节指定错误码。
- 筛选条件为空返回验证错误。
- 导出文件写入 MinIO export bucket。
- `expires_at` 为受理后 24 小时。
- 导出动作本身写入 `audit_logs`。

**依赖：** Django ORM、Celery、MinIO 客户端、分页、幂等、错误码、脱敏。

### permissions 模块

**职责：** 提供角色与接口域的基础访问规则，并委托抽象契约获取最终权限。

**规则：**

| 角色 | `/me/*` | `/teaching/*` | `/admin/*` |
|---|---|---|---|
| USER | SELF | NONE | NONE |
| ORG_SUB_ADMIN | SELF | AUTHORIZED | NONE |
| ORG_ADMIN | SELF | ALL | NONE |
| SYSTEM_ADMIN | SELF | NONE | ALL |

**依赖：** `errors`、Provider 契约。

### API 层

**职责：** 暴露健康检查、审计检索与审计导出接口。

**路由：**

```text
GET  /admin/health
GET  /admin/audit-logs
POST /admin/audit-logs/export
```

**依赖：** `responses`、`pagination`、`audit`、`permissions`、`idempotency`。

## 模块交互

### 同步请求链路

```text
客户端
  → RequestID/TraceID 中间件
  → 权限基类 / 幂等装饰器 / 业务视图
  → 统一异常处理器
  → JSON 响应 + X-Request-ID
  → 结构化日志
```

1. 中间件生成或透传标识并写入上下文。
2. 权限基类通过延迟加载的 Provider 获取身份与权限。
3. 写操作可启用幂等装饰器。
4. 视图使用统一响应与分页。
5. 异常统一转换为错误信封，不返回 HTML。
6. 响应完成后输出脱敏 JSON 日志。

### Outbox 链路

```text
业务事务
  → publish_outbox(OutboxMessage)
  → outbox_events 插入
  → 业务事务提交/回滚
  → 后台投递器扫描 PENDING
  → OutboxTransport 发布
  → 更新 PUBLISHED / FAILED / DEAD
```

- Outbox 写入与业务事实使用同一个数据库连接和事务。
- 业务回滚时 Outbox 插入一起回滚。
- 投递器与业务模块解耦，只处理通用字段与载荷。

### 审计链路

```text
请求 / 异常 / 导出任务
  → record_audit(AuditRecord)
  → audit_logs 仅追加插入
  → 管理员查询 / 导出
```

- 成功、拒绝与失败都调用统一记录函数。
- 数据库触发器阻止更新与删除。
- 导出任务通过 Celery 异步执行，通过 Redis 保存 operation 状态。

## 文件组织

```text
agent/backend/apps/common/
├── __init__.py
├── apps.py
├── constants.py
├── responses.py
├── errors.py
├── context.py
├── middleware.py
├── logging.py
├── pagination.py
├── idempotency.py
├── models.py
├── outbox.py
├── outbox_transport.py
├── audit.py
├── audit_export.py
├── permissions.py
├── providers.py
├── serializers.py
├── views.py
├── urls.py
└── tests/
    ├── test_responses.py
    ├── test_errors.py
    ├── test_context.py
    ├── test_logging.py
    ├── test_pagination.py
    ├── test_idempotency.py
    ├── test_outbox.py
    ├── test_audit.py
    ├── test_permissions.py
    └── test_api.py
```

配置侧新增：

```text
agent/backend/config/settings/base.py
├── COMMON_PRINCIPAL_PERMISSION_PROVIDER
├── COMMON_AUDITABLE_ACTOR_PROVIDER
├── COMMON_IDEMPOTENCY_TTL_SECONDS
├── COMMON_OUTBOX_BATCH_SIZE
├── COMMON_AUDIT_EXPORT_MAX_RECORDS
└── COMMON_AUDIT_EXPORT_TTL_SECONDS
```

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 应用形态 | Django app `apps.common` | 与现有工程一致，业务模块可直接复用横切能力。 |
| 表结构 | 非托管模型映射冻结表 | 不生成迁移、不修改 V4.0 结构，满足表冻结约束。 |
| 通用幂等 | Redis db 0 + Lua + TTL | 表结构已冻结，Redis 适合短期状态、锁与并发控制。 |
| 并发控制 | Redis 原子创建 `PENDING` | 同一 key 并发请求只执行一次业务。 |
| 响应信封 | 显式构造函数 | 成功与错误均输出数字 `code`，并集中维护数字码唯一性。 |
| C13 处理 | 数字码对外，符号名作内部别名 | 已按第 10、15 章数字码裁决；保留符号名便于代码阅读与测试定位。 |
| 请求上下文 | `contextvars` | 支持同步与异步请求，不需要业务层层传参。 |
| 日志 | 标准 logging + JSON formatter | 减少依赖，便于在出口统一脱敏。 |
| Outbox 发布 | 当前事务内插入 | 与业务事实原子提交或回滚，符合唯一合法副作用通道要求。 |
| Outbox 投递 | 抽象 Transport + Redis Streams 实现 | 保持通用性，后续可替换为独立消息系统。 |
| 审计修正 | 仅新增行 | 尊重数据库触发器的仅追加约束。 |
| 身份与权限 | settings 字符串路径延迟加载 | 避免 common import identity，消除循环依赖。 |
| 权限规则 | common 保存基础角色矩阵 | 角色矩阵是接口横切规则，最终数据范围仍由 identity 提供。 |
| 审计导出 | Celery + MinIO export bucket | 异步生成、独立存储、24 小时有效期与权限隔离。 |
| 测试 | 单元测试 + 数据库/Redis/MinIO 集成测试 | 覆盖事务、触发器、并发、导出文件等关键行为。 |

## spec 覆盖对照

| spec 需求 | plan 归属 |
|---|---|
| F1 | responses、middleware、API 层 |
| F2 | errors |
| F3 | context、middleware、outbox、audit |
| F4 | logging、middleware |
| F5 | context |
| F6 | pagination |
| F7 | idempotency |
| F8 | idempotency |
| F9 | models、outbox |
| F10 | outbox、outbox_transport |
| F11 | audit、models |
| F12 | audit、views、serializers |
| F13 | audit、audit_export、views |
| F14 | providers、permissions |
| F15 | permissions |

## 风险与约束

- `outbox_events.assignment_id`、`instance_id` 及 `audit_logs` 中的同名列是冻结数据库协议，必须原样映射；common 将其视为不透明 ID，不引入业务语义。
- 审计导出 100,000 条上限需使用流式写入，避免一次性占用过多内存。
- Outbox 投递器需避免多实例重复投递；实现时使用稳定排序加数据库行级条件更新作为领取锁。
- 审计导出的 24 小时文件有效性依赖对象存储桶生命周期策略；common 生成 `expires_at` 并使用不超过 24 小时的访问 URL，不主动修改桶策略。
- C13 已裁决：错误信封对外 `code` 必须为数字码；符号名不得直接输出到响应。
