# M1-membership 团队成员模块 Spec

## 背景

M1-common 与 M1-identity 已交付。当前 identity 通过 `MembershipService` Protocol 调用成员能力，但默认使用 `DeniedMembershipService` 兜底，无法提供真实成员身份。需要将成员资格从 identity 中拆出，交付独立的 `apps.membership`，支撑单团队成员申请、审核、直接添加、退出、移除，以及全平台共用的 ACTIVE 成员实时裁决。

数据库 V4.0 已冻结。本模块只拥有 `team_settings` 与 `team_memberships` 两张表；用户信息必须通过 identity 领域服务获取，不能直接读取用户表。会话撤销只能通过 Outbox 事件交由 M4-B 处理，不能直接访问其表或 Redis。

## 目标

- 提供单团队成员资格全生命周期能力，`team_id` 恒为 `1`。
- 为 identity 提供 `get_membership`、`unverified_start_policy`、`revoke_authentication_sessions` 三个既有接缝实现。
- 为 M2/M3/M4/M5 提供稳定领域服务，包括实时 ACTIVE 判定、活动成员 ID 获取、ACTIVE 断言、阻断摘要与团队设置读取。
- 所有写操作具备幂等、审计、Outbox、并发安全与明确状态机约束。
- 保持 identity 现有测试不回归，并新增 membership 单元、接口、状态机与并发测试。

## 功能需求

- F1 成员状态机：集中维护 `PENDING/ACTIVE/REJECTED/EXITED/REMOVED` 状态常量与显式转移表；仅允许规定转移，非法转移返回状态冲突，禁止散落状态判断。
- F2 用户端成员查询：已认证用户只能查询自己的成员记录，支持状态过滤与分页；返回自身记录明细及 `blocking_summary`，不得查看他人记录。
- F3 用户申请：仅 `USER` 可申请；提交前校验无 `ACTIVE` 且无 `PENDING`；成功创建 `PENDING` 记录并向管理员发出申请通知；重复申请按既有错误码与幂等契约处理。
- F4 重新申请：处于 `REJECTED/EXITED/REMOVED` 的用户可在团队策略允许时重新申请，走新的 `PENDING` 转移，不覆盖历史事实。
- F5 审核申请：仅 `ORG_ADMIN` 可审核 `PENDING` 申请；`APPROVE` 转 `ACTIVE`，`REJECT` 转 `REJECTED` 且审核备注必填；已处理申请返回状态冲突；同一幂等键重放返回原响应。
- F6 直接添加：仅 `ORG_ADMIN` 可按用户名直接添加；目标用户必须存在、状态为 `ACTIVE` 且未删除；成功创建或恢复为 `ACTIVE` 成员，并通知该成员。
- F7 成员列表：教学端支持分页、状态多选、关键词搜索、摘要统计；手机号与邮箱必须脱敏；`ORG_SUB_ADMIN` 只能查看授权任务关联的成员子集。
- F8 申请列表：教学端仅返回申请来源的 `PENDING` 记录，按申请时间最早优先；可查询已拒绝申请用于追溯。
- F9 成员退出：仅 `ACTIVE` 成员可主动退出；退出前执行阻断检查并将结果写入 `last_block_check_json`；检查与状态更新在同一事务内完成。
- F10 成员移除：仅 `ORG_ADMIN` 可移除；移除前执行阻断检查、保护最后一名有效 `ORG_ADMIN`，并记录移除时间与原因；历史任务数据保留。
- F11 阻断检查：根据退出与移除规则返回具体阻断事项摘要，包括未完成实验、活动实例、待审核、归档、销毁等；不得只返回笼统错误。
- F12 实时成员裁决：提供 `is_active_member`、`get_active_membership_id`、`assert_member_active`；快照仅用于留痕，不能替代任务发布或启动时的实时校验。
- F13 团队设置读取：提供 `get_team_settings`，至少支持读取未实名认证启动策略及后续模块需要的团队默认配置。
- F14 identity 接缝：实现既有 Protocol 三个方法；`get_membership` 返回 `membership_id` 与 `status`，无记录时返回 `None`；`unverified_start_policy` 返回 `DENIED/READ_ONLY/ALLOWED`；禁用用户时发布会话撤销 Outbox 事件。
- F15 领域事件：申请、审核、直接添加、退出、移除成功时发布对应 Outbox 事件，并保证同一业务事实仅发布一次。
- F16 审计：所有写操作记录审计，包含 `request_id`、`trace_id` 与业务对象 ID，且不落凭据、Token 或未脱敏敏感信息。

## 非功能需求

- N1 兼容性：Python 3.11+，目标运行环境 Python 3.12 / Django 5 / DRF。
- N2 数据纪律：模型 `managed = False`，不生成 migration，不改冻结表结构；不新增表。
- N3 幂等：所有写接口使用 common 幂等装饰器；相同键且相同摘要时重放原响应，相同键不同摘要返回幂等冲突。
- N4 并发：申请唯一性、审核、退出、移除、最后管理员保护均需并发安全；必要时使用行锁或数据库约束兜底。
- N5 安全：每次写操作独立校验动作权限与数据范围，不信任前端传入的角色、归属或用户 ID；错误响应不泄露内部细节。
- N6 响应契约：统一 `/api/v1` 前缀、统一信封与 `data.items` 分页结构；时间为 RFC3339 UTC 带时区偏移或 `Z`；字段与枚举为 snake_case。
- N7 错误码：只使用 common 已登记错误码；最后管理员保护返回 `LAST_TEAM_ADMIN_PROTECTED`，成员变更阻断返回 `MEMBERSHIP_CHANGE_BLOCKED`。
- N8 测试：覆盖状态机、幂等、并发、越权、阻断、快照与实时校验、事件发布、identity 回归；应用服务与命令覆盖率不低于 80%。
- N9 静态质量：`ruff format --check` 与 `ruff check` 必须通过。

## 不做的事

- 不建立多团队、组织架构、团队 CRUD、课程、班级或自定义角色。
- 不新增或修改数据库表、字段、索引和约束。
- 不直接读写 identity 的用户表或其他模块业务表。
- 不直接删除或修改 workspace access session，仅通过 Outbox 事件协调。
- 不实现 M4-B 会话消费、M2/M3/M4/M5 的事件消费逻辑。
- 不实现前端页面，不修改冻结 UI 设计。
- 不新增三方依赖。

## 未决冲突与保守策略

- C8：`ORG_SUB_ADMIN` 是否拥有审核权。规格采用最小保守策略：仅可查看授权任务范围内的成员子集，不可审核、添加、移除。
- C9：`join_source` 对外枚举值存在文档差异。存储使用 `APPLY/DIRECT/IMPORT`，如需对外映射则集中在 membership 常量层处理。
- C11：接口示例中的业务可读 ID 与数据库 BIGINT 主键存在差异。以数据库 V4.0 为准。
- C12：重复申请及阻断错误码文档冲突。以 common 错误字典为准，统一使用 `MEMBERSHIP_CHANGE_BLOCKED`。
- C13：最后管理员保护错误码文档冲突。以 common 错误字典为准，统一使用 `LAST_TEAM_ADMIN_PROTECTED`。

## 验收标准

- AC1 状态机全部合法转移成功，非法转移被拒绝且不改变数据库状态。
- AC2 用户不能查看、申请、审核、修改或移除他人成员记录；非授权角色访问教学端写接口返回 `FORBIDDEN`。
- AC3 同一用户不存在并存的多条 `PENDING` 或 `ACTIVE` 记录；重复申请不产生新事实。
- AC4 同一幂等键并发审核两次，仅处理一次，第二次返回首次状态与响应体。
- AC5 退出时存在 `ASSIGNED` 至 `UNDER_REVIEW` 的实验任务即被阻断，并返回具体阻断事项。
- AC6 移除时存在 `PROVISIONING/RUNNING/SUBMITTED` 的实验任务即被阻断，并返回具体阻断事项。
- AC7 并发移除最后一名有效 `ORG_ADMIN` 时，仅一个请求成功，其余返回 `LAST_TEAM_ADMIN_PROTECTED`。
- AC8 成员被移除后，历史快照保留，但 `is_active_member` 返回 false，任务启动被实时校验拒绝。
- AC9 退出与移除成功后，会话撤销 Outbox 事件恰好发布一次，且本模块不直接访问会话存储。
- AC10 `IDENTITY_MEMBERSHIP_PROVIDER` 指向 membership 实现后，identity 全量测试通过。
- AC11 所有写接口具备审计与幂等测试，事件仅发布一次。
- AC12 `ruff format --check`、`ruff check`、membership 测试与覆盖率检查全部通过。
