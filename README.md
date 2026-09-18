# agent

## common 模块

`backend/apps/common` 是 M1~M6 共用的横切底座，只提供可脱离业务复用的基础能力，不导入、不实现、不耦合任何业务模块。数据库模型均映射 V4.0 冻结表，并使用 `managed = False`；本阶段禁止生成 migration。

### 能力清单

- 统一响应：成功、列表、异步受理与错误信封，成功 `code` 固定为整数 `0`。
- 统一错误：数字错误码、HTTP 状态与默认消息集中在 `apps.common.errors`。
- 请求追踪：`X-Request-ID`、`X-Trace-ID` 生成与透传，响应头回写。
- 结构化日志：JSON 输出、上下文字段注入与敏感字段脱敏。
- 分页：参数校验、排序白名单、页大小上限与稳定排序。
- 幂等：Redis 记录请求摘要，支持并发互斥、结果回放与 TTL。
- 事务性 Outbox：数据库事务内写入事件，异步投递、重试与 DEAD 状态。
- 审计：统一记录、脱敏、检索与异步导出。
- Provider 契约：身份与权限由业务侧通过 settings 注入，common 不实现认证。

## membership 模块

`backend/apps/membership` 负责单团队成员资格生命周期、`ACTIVE` 成员实时裁决、阻断检查与 identity 成员接缝。两张业务表映射 V4.0 冻结结构并使用 `managed = False`，不生成 migration。

- 用户端：成员记录查询、申请/重新申请、主动退出。
- 教学端：成员与申请列表、审核、直接添加、移除。
- 安全：服务端独立校验角色与数据范围，手机号/邮箱脱敏，写操作幂等并落审计。
- 事件：业务事实与 Outbox 事件同事务写入；会话撤销只发布事件给 M4-B。
- 接缝：`IDENTITY_MEMBERSHIP_PROVIDER` 指向 `apps.membership.identity_provider.MembershipIdentityProvider`。

模块设计、API、领域服务、冲突保守策略与测试说明见 `backend/apps/membership/README.md`。

## 后端开发

```powershell
Set-Location agent\backend
.venv\Scripts\python.exe -m pytest apps\common -q
.venv\Scripts\python.exe -m pytest apps\membership -q
.venv\Scripts\python.exe -m pytest apps\identity -q
.venv\Scripts\python.exe -m ruff format --check apps\common
.venv\Scripts\python.exe -m ruff format --check apps\membership
.venv\Scripts\python.exe -m ruff check apps\common
.venv\Scripts\python.exe -m ruff check apps\membership
```

详细使用方式见 `backend/README.md`。
