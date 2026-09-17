# common 模块 Checklist

> 每一项通过运行代码或观察行为验证，聚焦系统行为。C13 已裁决：错误响应对外 `code` 采用数字码，符号名仅作为内部常量别名。

## 实现完整性

- [x] [响应信封] 四类响应构造能力已实现并可直接调用。（验证：`.venv\Scripts\python.exe -m pytest apps/common/tests/test_responses.py -q`）
- [x] [错误字典] 数字错误码、符号名、HTTP 状态与默认消息集中定义，无重复数字码。（验证：`.venv\Scripts\python.exe -m pytest apps/common/tests/test_errors.py -q`）
- [x] [请求上下文] `request_id` 与 `trace_id` 的生成、透传、响应头注入和上下文清理已实现。（验证：`.venv\Scripts\python.exe -m pytest apps/common/tests/test_context.py -q`）
- [x] [结构化日志] JSON 日志、脱敏函数和上下文字段注入已实现。（验证：`.venv\Scripts\python.exe -m pytest apps/common/tests/test_logging.py -q`）
- [x] [分页器] 参数校验、白名单排序、稳定排序、页大小截断与分页输出已实现。（验证：`.venv\Scripts\python.exe -m pytest apps/common/tests/test_pagination.py -q`）
- [x] [幂等能力] Redis 记录、摘要校验、并发互斥、结果回放与 TTL 已实现。（验证：`.venv\Scripts\python.exe -m pytest apps/common/tests/test_idempotency.py -q`）
- [x] [非托管模型] `OutboxEvent` 与 `AuditLog` 映射 V4.0 冻结表且不生成 migration。（验证：`rg -n "managed = False|db_table" apps/common/models.py` 且 `rg --files apps/common | rg "migrations"` 无结果）
- [x] [Outbox] 事务内发布、到期领取、传输投递、重试与 DEAD 状态已实现。（验证：`.venv\Scripts\python.exe -m pytest apps/common/tests/test_outbox.py -q`）
- [x] [审计记录] 统一 `record_audit`、脱敏、用户代理摘要与仅追加语义已实现。（验证：`.venv\Scripts\python.exe -m pytest apps/common/tests/test_audit.py -q`）
- [x] [权限契约] `PrincipalPermissionProvider`、`AuditableActorProvider` 与角色矩阵已实现。（验证：`.venv\Scripts\python.exe -m pytest apps/common/tests/test_permissions.py -q`）
- [x] [API 能力] 健康检查、审计检索、审计导出路由与视图已挂载。（验证：`.venv\Scripts\python.exe -m pytest apps/common/tests/test_api.py -q`）
- [x] [配置集成] 中间件、异常处理器、Provider 路径与 common 参数已接入 settings。（验证：`.venv\Scripts\python.exe manage.py check --settings=config.settings.test`）

## 统一响应验收

- [x] 成功响应包含 `code: 0`、`message: "ok"`、`data`、`request_id`。（验证：响应测试逐字段断言）
- [x] 列表响应 `data` 只包含 `items`、`page`、`page_size`、`total`。（验证：响应测试断言键集合）
- [x] 异步 202 响应包含 `operation_id`、`trace_id`、`status: "ACCEPTED"`。（验证：导出 API 测试断言）
- [x] 错误响应 `code` 为文档指定数字码，`message` 人类可读，`request_id` 存在。（验证：错误处理器测试）
- [x] 成功 `code` 与错误 `code` 均为整数，符号名不出现在响应中。（验证：响应与错误测试）
- [x] 任意异常均返回约定错误信封，不出现 HTML 错误页或堆栈。（验证：使用未知异常请求测试 API）

## 错误码验收

- [x] 第 24.1、24.2 节通用错误码与业务补充错误码已全部收录。（验证：错误码清单测试）
- [x] 数字错误码唯一。（验证：错误码字典测试使用集合长度比较）
- [x] HTTP 状态与数字码映射逐条断言。（验证：参数化测试覆盖每个 `ErrorCode`）
- [x] 业务模块只能引用 `apps.common.errors`，不能自造错误码字符串。（验证：静态检查业务模块错误响应来源）
- [x] 数字码与符号名映射表存在且可维护。（验证：错误码映射测试）
- [x] 未知异常返回内部错误数字码与 500 HTTP 状态。（验证：异常处理器测试）

## 请求追踪与日志验收

- [x] 请求未携带 `X-Request-ID` 时生成 UUIDv4。（验证：测试请求后检查响应头格式）
- [x] 请求携带合法 `X-Request-ID` 时原样透传。（验证：测试请求后比较响应头）
- [x] 响应头包含 `X-Request-ID`。（验证：API 集成测试）
- [x] 上下文可读取 `request_id`、`trace_id`、用户标识与动作。（验证：上下文单元测试）
- [x] 异步任务与 Outbox 载荷携带 `trace_id`。（验证：Outbox 测试）
- [x] 日志为合法 JSON。（验证：捕获日志并执行 JSON 解析）
- [x] 日志包含 `request_id`、`trace_id`、用户标识、动作、耗时。（验证：日志字段断言）
- [x] 日志中不存在密码、Token、Cookie、Authorization 头、API 密钥明文。（验证：构造敏感字段请求后扫描捕获日志）
- [x] 嵌套字典和列表中的敏感字段均被脱敏。（验证：脱敏函数参数化测试）
- [x] 请求结束后上下文被清理，避免污染后续请求。（验证：连续请求测试）

## 分页验收

- [x] 默认 `page` 为 1、`page_size` 为 20。（验证：分页参数测试）
- [x] `page_size` 小于 1 时返回验证错误。（验证：分页参数测试）
- [x] `page_size` 大于 100 时截断为 100。（验证：分页参数测试）
- [x] `order` 只允许 `asc` 与 `desc`。（验证：非法 order 返回验证错误）
- [x] `sort` 只允许白名单字段。（验证：非法 sort 返回验证错误）
- [x] 默认排序附带唯一 ID，保证翻页稳定。（验证：分页查询测试）
- [x] 连续翻页无重复记录。（验证：收集多页 ID 并断言无重复）
- [x] 连续翻页无丢失记录。（验证：多页 ID 并集等于全量 ID）
- [x] 分页结果转换成统一列表信封。（验证：分页与响应集成测试）

## 幂等验收

- [x] 幂等 key 由用户标识、接口范围、`Idempotency-Key` 组成。（验证：检查 Redis key 格式测试）
- [x] `Idempotency-Key` 必须为 UUID 格式。（验证：非法 key 返回验证错误）
- [x] Redis 记录包含请求摘要、状态、原 HTTP 状态码、原响应体。（验证：读取测试 Redis 记录）
- [x] Redis TTL 不低于 24 小时。（验证：检查 TTL 秒数）
- [x] 同一 key、同一摘要、并发两次请求只执行一次业务。（验证：并发请求并统计视图执行次数）
- [x] 第二次请求回放首次 HTTP 状态码与响应体。（验证：并发测试断言两个响应一致）
- [x] 同一 key、不同摘要返回 409 与指定数字错误码。（验证：修改请求体后重放）
- [x] TTL 过期后同一 key 可重新执行业务。（验证：测试中调整 Redis TTL 后重放）
- [x] GET、HEAD、OPTIONS 不要求 `Idempotency-Key`。（验证：三种方法直接调用）
- [x] 业务失败也被记录并可在重试时回放原错误响应。（验证：让视图抛出异常后再次请求）
- [x] 幂等装饰器按视图启用，不做全局强制。（验证：未装饰写操作可重复执行）

## Outbox 验收

- [x] `OutboxEvent` 模型为 `managed = False`，表名为 `outbox_events`。（验证：模型元数据断言）
- [x] `OutboxEvent` 字段严格对应 V4.0 的 16 列。（验证：模型字段清单测试）
- [x] `publish_outbox` 在无活动事务时拒绝写入。（验证：非事务调用返回内部错误）
- [x] `publish_outbox` 在业务事务内插入记录。（验证：事务测试查询记录存在）
- [x] 业务事务回滚时 Outbox 记录一起回滚。（验证：触发异常后查询记录不存在）
- [x] `event_id` 为 UUIDv4 且唯一。（验证：事件 ID 格式与唯一性测试）
- [x] 载荷包含 `event_id`、`event_type`、`occurred_at`、`trace_id`。（验证：解析 payload JSON 断言字段）
- [x] 按场景携带 assignment ID、instance ID 或 operation ID。（验证：构造不同 `OutboxMessage` 测试）
- [x] 载荷中的敏感值完成脱敏。（验证：载荷包含 Token 后检查已替换）
- [x] 到期 `PENDING` 事件能被批量领取。（验证：投递器测试统计领取数量）
- [x] 多实例领取不重复处理同一事件。（验证：并发调用投递器并统计成功次数）
- [x] 投递成功后状态为 `PUBLISHED` 且 `published_at` 有值。（验证：传输成功后查询记录）
- [x] 投递失败时尝试计数递增。（验证：传输抛异常后查询记录）
- [x] 失败后按指数退避更新 `available_at`。（验证：连续失败后比较时间）
- [x] 第 10 次失败后状态为 `DEAD`。（验证：循环触发失败并断言状态）
- [x] `last_error` 完成脱敏。（验证：注入含 Token 的异常消息后查询）
- [x] common 不包含任何具体业务事件消费逻辑。（验证：静态检查无业务事件分支）

## 审计记录验收

- [x] `AuditLog` 模型为 `managed = False`，表名为 `audit_logs`。（验证：模型元数据断言）
- [x] `AuditLog` 字段严格对应 V4.0 的 19 列。（验证：模型字段清单测试）
- [x] 统一审计函数写入 `request_id`、`trace_id`、用户、角色、动作、目标类型与 ID。（验证：审计记录字段断言）
- [x] SUCCESS、DENIED、FAILURE 均写入审计。（验证：三种结果分别调用并查询）
- [x] 系统或编排写入时 `actor_user_id` 可为空。（验证：空操作者测试）
- [x] `before_json`、`after_json`、`reason` 完成脱敏。（验证：构造敏感字段并断言）
- [x] IP 地址按统一规则脱敏后存储。（验证：IPv4 与 IPv6 样例测试）
- [x] 用户代理只保存摘要，不保存原文。（验证：摘要长度与原文不存在）
- [x] `occurred_at` 与 `created_at` 使用 UTC。（验证：时区断言）
- [x] 对 `audit_logs` 执行 UPDATE 会触发 `AUDIT_LOG_APPEND_ONLY`。（验证：集成数据库执行 UPDATE）
- [x] 对 `audit_logs` 执行 DELETE 会触发 `AUDIT_LOG_APPEND_ONLY`。（验证：集成数据库执行 DELETE）
- [x] common 不提供审计 UPDATE/DELETE 封装。（验证：审计模块接口静态检查）

## 审计检索验收

- [x] 仅 `SYSTEM_ADMIN` 可访问审计检索。（验证：其他角色返回 FORBIDDEN）
- [x] 支持用户、动作、目标类型、目标 ID、请求 ID、追踪 ID 筛选。（验证：构造多条记录并检索）
- [x] 支持创建时间范围筛选。（验证：边界时间数据测试）
- [x] 支持脱敏 IP 筛选。（验证：构造 IP 后检索）
- [x] 支持 assignment ID 关联查询。（验证：构造相关记录并断言全部返回）
- [x] 支持 instance ID 关联查询。（验证：构造相关记录并断言全部返回）
- [x] 默认按 `created_at` 倒序。（验证：多时间记录顺序断言）
- [x] 排序字段走白名单，非法字段被拒绝。（验证：非法 `sort_by` 返回验证错误）
- [x] 翻页无重复且无丢失。（验证：多页 ID 与全量 ID 比较）
- [x] 检索结果为统一列表信封。（验证：响应结构断言）

## 审计导出验收

- [x] 仅 `SYSTEM_ADMIN` 可触发导出。（验证：其他角色返回 FORBIDDEN）
- [x] `filters` 为空返回 40004 对应数字码与 HTTP 400。（验证：空筛选请求）
- [x] 导出数量超过 100,000 返回 42205 对应数字码与 HTTP 422。（验证：构造超过上限的结果集）
- [x] 请求返回 202 与统一异步受理信封。（验证：触发导出并断言响应）
- [x] 受理响应包含 `operation_id`、`trace_id`、`status: "ACCEPTED"`。（验证：异步 202 响应断言）
- [x] 导出任务异步执行，不阻塞请求线程。（验证：Celery eager/eager-false 测试）
- [x] CSV 格式输出包含所有检索列并正确转义。（验证：读取导出文件并解析）
- [x] JSON 格式输出为合法 JSON 数组或对象。（验证：读取导出文件并解析）
- [x] 默认脱敏 `ip_address` 与 `user_agent`。（验证：导出内容断言）
- [x] 指定 `mask_fields` 按指定字段脱敏。（验证：自定义字段测试）
- [x] 文件上传至 MinIO export bucket。（验证：检查对象 key 与 bucket）
- [x] `expires_at` 为受理后 24 小时。（验证：比较完成态时间）
- [x] 完成态返回 `file_key`、`file_url`、`file_size_bytes`、`total_records`、`masked_fields`、`expires_at`。（验证：查询导出完成态）
- [x] 同一幂等 key 重放首次导出结果。（验证：重复请求比较响应）
- [x] 导出动作写入 `audit_logs`。（验证：查询目标为导出操作的审计行）
- [x] 审计行记录导出人、筛选条件与导出记录数。（验证：解析 `after_json` 或相关审计字段）

## 权限与边界验收

- [x] USER 可访问 `/me/*` 本人范围，不能访问教学与管理接口。（验证：角色矩阵参数化测试）
- [x] ORG_SUB_ADMIN 可访问 `/me/*` 本人范围与授权任务范围，不能访问管理接口。（验证：角色矩阵测试）
- [x] ORG_ADMIN 可访问 `/me/*` 本人范围与教学全部范围，不能访问管理接口。（验证：角色矩阵测试）
- [x] SYSTEM_ADMIN 可访问 `/me/*` 本人范围与全部管理接口，不能访问教学接口。（验证：角色矩阵测试）
- [x] `PrincipalPermissionProvider` 通过 settings 字符串路径延迟加载。（验证：使用测试 Provider 配置）
- [x] `AuditableActorProvider` 通过 settings 字符串路径延迟加载。（验证：使用测试 Provider 配置）
- [x] Provider 加载失败返回统一内部错误。（验证：配置不存在路径）
- [x] common 源码不导入任何业务模块。（验证：`rg -n "from apps\\.(?!common)|import apps\\.(?!common)" apps/common` 无匹配）
- [x] common 只直接读写 `outbox_events`、`audit_logs` 与 Redis 幂等记录。（验证：代码静态检查数据库表名）
- [x] common 源码不出现成员、任务、报告、实例、模板等业务语义词。（验证：业务词扫描；冻结数据库列名除外）
- [x] common 不实现身份认证或用户资料逻辑。（验证：模块职责与导入检查）

## 配置与集成验收

- [x] request/trace 中间件已加入 Django `MIDDLEWARE`。（验证：settings 检查）
- [x] DRF 异常处理器已接入配置。（验证：settings 检查与异常请求测试）
- [x] Provider 字符串路径配置存在。（验证：settings 检查）
- [x] 幂等 TTL、Outbox 批量、审计导出上限与 TTL 配置存在。（验证：settings 检查）
- [x] common 路由已挂载到项目 URL 配置。（验证：Django check 与路由测试）
- [x] 测试环境可在无 MySQL、Redis、MinIO 外部服务时运行单元测试。（验证：单元测试命令）
- [ ] 集成测试能连接 MySQL、Redis db 0/db 1 与 MinIO。（验证：集成测试命令）
- [ ] Redis db 0 与 db 1 逻辑库隔离保持不变。（验证：配置校验与集成测试）
- [x] Django check 无错误。（验证：`.venv\Scripts\python.exe manage.py check --settings=config.settings.test`）

## 文档验收

- [x] 根 README 说明 common 能力清单与使用方式。（验证：检查 `agent/README.md`）
- [x] 后端 README 说明响应、错误码、分页、幂等、Outbox 与审计使用方式。（验证：检查 `agent/backend/README.md`）
- [x] README 记录 Provider 与 common 配置项。（验证：搜索配置名）
- [x] README 明确 V4.0 表为非托管映射且不生成 migration。（验证：文档文本检查）
- [x] README 不描述业务模块实现。（验证：人工审阅）

## 质量验收

- [x] Ruff 格式检查通过。（验证：`.venv\Scripts\python.exe -m ruff format --check .`）
- [x] Ruff 静态检查通过。（验证：`.venv\Scripts\python.exe -m ruff check .`）
- [x] common 单元测试通过。（验证：`.venv\Scripts\python.exe -m pytest apps/common -q`）
- [x] common 覆盖率不低于 80%。（验证：`.venv\Scripts\python.exe -m pytest apps/common -q --cov=apps.common --cov-report=term-missing`）
- [ ] 数据库、Redis、MinIO 集成测试通过。（验证：在服务可用环境执行集成测试）
- [x] 源码扫描未发现密钥明文模式。（验证：`rg -n "(password|token|cookie|authorization|api[_-]?key).{0,20}(=|:)" apps/common` 并人工复核）
- [x] 仓库未新增 migration。（验证：`rg --files apps/common | rg "migrations"` 无结果）
- [x] 所有接口响应不返回 HTML 错误页。（验证：API 错误场景测试）

## 端到端场景

### 场景一：统一请求与审计检索

- [x] 管理员携带 `X-Request-ID` 请求审计检索。（验证：观察响应头与响应体）
- [x] 系统返回统一列表信封与相同 `request_id`。（验证：断言请求 ID）
- [x] 多条件筛选返回目标审计记录。（验证：断言记录内容）
- [x] 翻页后所有目标记录无重复、无丢失。（验证：比较页内 ID 与全量 ID）
- [x] 日志输出结构化 JSON 且敏感字段脱敏。（验证：读取捕获日志）

### 场景二：幂等写操作

- [x] 用户携带 UUID `Idempotency-Key` 发起写请求。（验证：观察首次响应）
- [x] 业务执行一次并写入审计。（验证：统计视图执行次数与审计行数）
- [x] 同 key 同摘要再次请求回放首次响应。（验证：比较两次状态码与响应体）
- [x] 同 key 不同摘要返回 409 数字错误码。（验证：修改请求体后重放）
- [x] Redis 记录 TTL 不低于 24 小时。（验证：检查 Redis TTL）

### 场景三：Outbox 事务性发布

- [x] 业务事务内调用 `publish_outbox`。（验证：事务内查询事件存在）
- [x] 业务事务提交后事件状态为 `PENDING`。（验证：提交后查询）
- [x] 后台投递器将事件发布到传输层。（验证：检查传输记录）
- [x] 投递成功后事件状态为 `PUBLISHED`。（验证：查询事件）
- [x] 业务回滚时事件同步回滚。（验证：触发异常后查询事件不存在）

### 场景四：审计导出

- [x] 管理员提交导出筛选条件。（验证：观察 202 响应）
- [x] 系统返回 `operation_id` 与 `trace_id`。（验证：断言响应字段）
- [x] 异步任务生成 CSV 或 JSON 文件。（验证：读取生成文件）
- [x] 文件上传至 export bucket 且 `expires_at` 为 24 小时。（验证：检查对象与时间）
- [x] 导出动作落审计并记录筛选条件与记录数。（验证：查询审计行）
- [x] 同 key 重放导出请求，不重复生成文件。（验证：比较对象 key 与响应）

## 最终放行

- [x] 所有实现完整性项通过。
- [x] 所有行为验收项通过。
- [x] 所有端到端场景通过。
- [x] 覆盖率不低于 80%。
- [x] Ruff format 与 Ruff check 通过。
- [x] common 依赖边界检查通过。
- [x] C13 数字码协议检查通过。
- [x] 无 migration 新增。
- [x] 无密钥明文泄露。

## 实际验收记录

- 离线实现与行为验收已完成：`.venv\Scripts\python.exe -m pytest apps/common -q --cov=apps.common --cov-report=term-missing`，结果 `68 passed`，覆盖率 `92%`。
- Ruff 验收已完成：`.venv\Scripts\python.exe -m ruff format --check apps/common` 与 `.venv\Scripts\python.exe -m ruff check apps/common`，结果均通过。
- Django 配置验收已完成：`.venv\Scripts\python.exe manage.py check --settings=config.settings.test`，结果无错误。
- 边界验收已完成：common 未导入业务模块，未新增 migration；敏感词扫描命中项均为测试夹具或脱敏逻辑，无真实密钥泄露。
- 外部集成验收未执行：MySQL、Redis、MinIO 的真实服务联调仍需在服务全部可用后执行；当前 checklist 中相关 3 项保持未勾选。
