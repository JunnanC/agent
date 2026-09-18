# M1-membership 技术设计 Plan

## 架构概览

新增 `apps.membership`，作为单团队成员资格唯一后端模块。应用分层如下：

- `models.py`：映射冻结表 `team_settings`、`team_memberships`，全部 `managed = False`。
- `constants.py`：集中定义成员状态、来源、事件类型、状态转移、阻断类型与对外枚举映射。
- `serializers.py`：请求校验与响应序列化，负责字段约束、脱敏和 RFC3339 时间输出。
- `selectors.py`：只读查询，包括用户自身记录、教学端成员与申请列表、摘要统计。
- `services.py`：领域服务与应用服务，负责事务、状态机、阻断检查、权限断言、Outbox 与审计。
- `identity_provider.py`：实现 identity 既有 `MembershipService` Protocol，只做转发。
- `views.py` 与 `urls.py`：DRF API，使用 common 幂等、响应信封与 identity 权限接缝。
- `tests/`：状态机、服务、API、并发、越权、接缝与回归测试。

`identity` 不新增成员逻辑，继续通过 `apps.identity.services.membership.membership_service()` 动态加载 provider。配置指向 `apps.membership.identity_provider.MembershipIdentityProvider` 后，登录、`/me`、未实名启动策略与禁用用户会话撤销均走 membership 实现。

## 组件划分

### 数据模型

`TeamSettings`：

- 单例表，`id = 1`。
- 映射 V4.0 的 19 个字段。
- 不提供创建、删除或多实例查询入口；读取失败时按依赖不可用或资源不存在处理，不自动创建。

`TeamMembership`：

- 映射 V4.0 的 18 个字段。
- `team_id`、`reviewed_by_id`、`created_by_id` 使用整数外键语义，但模型侧不依赖跨 app 关联查询。
- `last_block_check_json` 只作为阻断检查时点的留痕快照，不作为实时裁决依据。
- 不生成 migration，不修改表、索引或约束。

### 状态机

在 `constants.py` 中定义：

- 成员状态：`PENDING`、`ACTIVE`、`REJECTED`、`EXITED`、`REMOVED`。
- 来源：`APPLY`、`DIRECT`、`IMPORT`。
- 转移表：
  - `None -> PENDING`：用户申请。
  - `REJECTED/EXITED/REMOVED -> PENDING`：重新申请。
  - `None -> ACTIVE`：`ORG_ADMIN` 直接添加。
  - `PENDING -> ACTIVE/REJECTED`：审核。
  - `ACTIVE -> EXITED/REMOVED`：退出或移除。

状态变更统一由服务层调用 `transition_membership()`；非法转移抛出 `STATE_CONFLICT`，并保持事务回滚。

### 查询与权限

- 用户端查询从访问令牌解析当前用户，强制 `user_id = actor.id`，忽略或拒绝伪造归属。
- 教学端读接口允许 `ORG_ADMIN` 查询全量；`ORG_SUB_ADMIN` 仅能查询授权任务关联成员子集，C8 裁决前不可执行写操作。
- 教学端写接口仅允许 `ORG_ADMIN`，并在服务层再次校验，不依赖路由或前端隐藏。
- 用户查找通过 identity 已有用户服务或选择器完成；membership 不直接导入 `User` ORM 查询。

## 核心接口

所有接口挂载于 `/api/v1`，响应使用 common 信封；列表使用 `data.items` 分页契约。

### 用户端

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/me/team-membership` | 当前用户自身成员记录、分页与 `blocking_summary` |
| POST | `/api/v1/me/team-membership/applications` | 申请或重新申请，幂等 |
| POST | `/api/v1/me/team-membership/exit` | 主动退出，幂等 |

### 教学端

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/teaching/team-members` | 成员分页、状态多选、关键词、摘要 |
| GET | `/api/v1/teaching/team-membership-applications` | 待审核申请，最早优先 |
| POST | `/api/v1/teaching/team-membership-applications/{id}/review` | 审核申请，幂等 |
| POST | `/api/v1/teaching/team-members` | 直接添加成员，幂等 |
| POST | `/api/v1/teaching/team-members/{membershipId}/remove` | 移除成员，幂等 |

## 领域服务

### 对外服务

- `is_active_member(user_id: int) -> bool`：实时查询当前 `ACTIVE` 状态。
- `get_active_membership_id(user_id: int) -> int | None`：返回活动成员 ID，供任务发布写快照。
- `assert_member_active(user_id: int) -> int`：根据当前状态抛出 `MEMBERSHIP_REQUIRED` 或 `MEMBERSHIP_PENDING`。
- `has_blocking_items(user_id: int) -> list[BlockItem]`：返回退出/移除前阻断摘要。
- `get_team_settings() -> TeamSettings`：返回单例团队配置。

### identity 接缝

`MembershipIdentityProvider`：

- `get_membership(user_id)`：返回 `{"membership_id": str(id), "status": status}`；无记录返回 `None`。
- `unverified_start_policy(membership_id)`：读取单例配置并返回 `DENIED/READ_ONLY/ALLOWED`。
- `revoke_authentication_sessions(user_id)`：只发布 `SESSION_REVOCATION_REQUESTED` Outbox 事件，不访问 M4-B 表或 Redis。

### 阻断检查

- 退出：检查 `ASSIGNED` 至 `UNDER_REVIEW` 区间内未完成任务。
- 移除：检查 `PROVISIONING/RUNNING/SUBMITTED` 状态任务。
- 输出结构包含 `type`、`assignment_id`、`status`、`reason`，写入响应并保存到 `last_block_check_json`。
- 检查与状态更新在同一事务内执行；成员行使用 `select_for_update()`。

## 模块交互

### common

- 响应：`success`、`paginated`、`accepted`。
- 错误：`ApiError` 与已登记 `ErrorCode`，不自造错误码。
- 幂等：`idempotent("membership:...")`。
- 审计：通过 `record_audit()` 写入动作、actor、对象 ID、request/trace ID。
- Outbox：`publish_outbox()` 与业务事实同事务发布。
- 分页：`parse_page_params()`、`paginate_queryset()`。

### identity

- 登录、`/me` 通过既有 provider 动态获取成员状态。
- 禁用用户时调用 provider 的会话撤销钩子。
- 用户信息、脱敏函数与认证角色校验复用 identity 已有能力。
- 修改 identity 文件仅限配置 provider 与必要测试适配，不迁移成员逻辑。

### M2/M3/M4/M5

- 任务发布通过 `get_active_membership_id()` 写快照。
- 任务启动和实例创建前通过 `assert_member_active()` 实时校验。
- M4-B 只消费 membership 发布的会话撤销事件。

## 技术决策

- 使用数据库唯一约束与 `select_for_update()` 共同保证并发安全；不新增约束。
- 所有状态更新限定 `update_fields`，避免覆盖并发字段。
- `previous_status` 在每次成功转移前写入，便于审计和回退分析。
- Outbox 事件包含 `aggregate_type`、`aggregate_id`、`event_type`、`event_id`、`payload`；消费者按 `event_id` 去重。
- API 使用显式状态码：申请 201，退出、审核、移除 200。
- 测试优先使用 SQLite 内存库与 mock 外部模块；数据库并发语义用事务测试或集成标记覆盖。

## 测试设计

- 状态机：全部合法转移、非法转移、`previous_status` 记录。
- API：参数校验、响应信封、分页、排序、脱敏、权限。
- 幂等：申请、审核、退出、移除同一键并发/重放。
- 并发：重复申请、审核竞争、退出/移除竞争、最后管理员保护。
- 阻断：退出与移除分别覆盖指定任务状态并验证具体阻断事项。
- 快照：保留 `team_membership_id`，实时 ACTIVE 判定变化。
- 事件：申请、审核、添加、退出、移除、会话撤销恰好一次。
- 越权：USER、ORG_SUB_ADMIN、ORG_ADMIN 边界。
- identity 回归：provider 指向新实现后全量 identity 测试。

## 风险与应对

- SQLite 测试无法完全模拟 MySQL 行锁：将并发逻辑集中在小函数，并用事务或竞争测试覆盖语义；必要时保留 MySQL 集成标记。
- `ORG_SUB_ADMIN` 授权范围数据尚未由 M2 提供：先实现接缝与保守过滤，无法确定范围时返回空集，不做写操作。
- 文档 ID 形态冲突：以 V4.0 BIGINT 为准，序列化层不引入新 ID 体系。
- 阻断检查依赖其他模块表：仅通过明确只读接缝查询，不直接写他人表；接口未就绪时用可替换 adapter，并在测试中注入假数据。
