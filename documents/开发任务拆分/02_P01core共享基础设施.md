# P01 core 共享基础设施

## 目标

实现全系统复用的事务一致性、幂等、并发、错误、审计、Outbox、补偿、对象资产和 trace 机制，不包含具体领域规则。

## 后端范围

- 初始 schema：`core_object_asset`、`core_object_purge_log`、`core_outbox_event`、`core_outbox_delivery`、`core_idempotency_record`、`core_audit_log`、`core_failure_record`、`core_compensation_task`。
- `VersionedModel`、`AppendOnlyModel`、row_version/CAS、统一异常映射、分页和脱敏工具。
- `TraceIdMiddleware`、W3C trace 透传、结构化日志 formatter；日志默认 stdout，由 P00 采集器写 MongoDB。
- Outbox relay、delivery lease、重试退避、补偿任务基类和 Celery 队列骨架。
- 对象资产登记、digest、扫描状态、保留期和 purge log；不实现具体业务上传。

## 前端范围

- `api-client` 的统一请求、CSRF、错误信封、trace_id 展示、ETag/If-Match。
- 幂等键在一次用户意图的重试中保持不变。
- 通用 loading/empty/error/403/409/412/428/429 组件和分页协议。

## 测试与验收

- AppendOnly 对已有行的 save/update/delete 被阻止；数据库账号权限方案有集成验证。
- 所有有副作用 POST 默认要求 Idempotency-Key；只允许架构 `08` 列出的五个例外。服务端在认证、Portal/Integration 准入和对象 scope 后查询幂等记录；相同 actor/auth-context/endpoint/key/digest 在状态与 If-Match 校验前重放原响应，不重复副作用，不同 digest 返回 `422`。
- 同一 row_version 并发更新一个成功、一个 `412`。
- 事务回滚不产生 Outbox；提交后才入队；消费者重复投递只处理一次。
- trace_id 贯穿 HTTP、Celery 和日志；Token、Cookie、IP、证件号递归脱敏。
- 空 MySQL 与 Redis 集成测试通过，不依赖 MongoDB 才能判定业务成功。

## 不做

- 不添加账号、课程、任务或审核业务字段。
- 不调用 Swarm、MinIO 业务对象、模型网关或邮件。

## 出口

后续所有 app 只通过 core 完成幂等、审计、错误、事件和补偿，不重复实现横切机制。
