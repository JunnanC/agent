# identity 模块 Plan

## 架构概览

- 新增 `apps.identity` Django 应用，作为身份事实源与权限裁决者。
- 复用 common 的统一响应、错误码、分页、幂等、审计、Outbox、日志脱敏与 Provider 契约。
- 六张 V4.0 表均建立非托管 Django 模型，不生成 migration。
- 认证使用 JWT 访问令牌与服务端存储的轮换刷新令牌；仅保存令牌哈希，不保存明文。
- 成员资格、团队策略、工作区会话、通知和文件访问通过外部模块领域服务接口完成，identity 不直接读写其他模块表。
- 批量导入、通知撤销与工作区会话撤销通过 common Outbox 事件解耦，由对应模块消费。

## 组件划分

- `models.py`：`User`、`Role`、`Permission`、`RolePermission`、`UserVerification`、`UserQuota` 非托管模型。
- `selectors.py`：用户、角色、权限、认证状态与配额的只读查询。
- `services/auth.py`：登录、刷新轮换、重放检测、登出与当前身份组装。
- `services/admin_users.py`：单条创建、批量导入受理、状态与角色变更。
- `services/permissions.py`：角色、权限码、数据范围、认证状态与外部团队策略的组合裁决。
- `services/quotas.py`：配额查询、上限调整与供编排模块调用的原子调整。
- `serializers.py`：请求校验、响应序列化、手机号与实名脱敏、C10 接口别名映射。
- `views.py` / `urls.py`：认证、管理用户、权限矩阵与配额 API。
- `permissions.py`：DRF 权限类，供 identity 与其他模块复用。
- `tasks.py`：Celery 批量导入与进度记录。
- `tests/`：单元测试、API 测试、权限矩阵测试、并发配额测试与覆盖率测试。

## 数据模型

- `User`：18 列严格使用 V4.0 字段名；唯一约束为 `username`、`phone`、`email`；软删除条件为 `deleted_at IS NOT NULL`。
- `Role` / `Permission` / `RolePermission`：只读字典；由初始化数据脚本维护，不提供管理 API。
- `UserVerification`：用户唯一记录；`verification_type` 与 `status` 参与权限裁决；展示层脱敏。
- `UserQuota`：用户唯一记录；字段严格使用 V4.0 名称；业务层保证 `0 <= used_x <= max_x`。
- `managed = False`，`migrations` 目录不创建。

## 令牌设计

- 访问令牌：JWT，默认 2 小时，声明包含 `user_id`、`role_code`、`membership_status`、`jti`。
- 刷新令牌：随机高熵令牌，默认 7 天；数据库仅存 SHA-256 哈希、用户、状态、轮换前驱标识与过期时间。
- 刷新成功后旧令牌立即标记轮换；同一旧令牌再次使用判定为重放，并撤销该用户全部活动认证会话。
- 登出幂等：撤销当前访问令牌 `jti` 与关联刷新令牌；重复登出直接返回成功。
- 访问令牌撤销状态由 identity 查询；工作区会话撤销通过外部模块事件完成。

## 权限模型

- `PrincipalPermissionProvider.can(user, action, resource_scope)`：依次校验用户有效、角色权限码、数据范围、认证状态与动作级外部策略。
- `AuditableActorProvider`：从 JWT 解析可审计操作者，忽略请求体中的用户、角色和归属声明。
- 数据范围：`SELF`、`AUTHORIZED`、`ALL`、`NONE`；默认拒绝。
- 团队未认证启动策略通过 membership 领域服务读取，不查询 `team_settings` 或 `team_memberships`。
- 提供通用 DRF 权限类：要求认证、要求系统管理员、要求动作权限、要求数据范围。

## API 设计

- `POST /auth/login`：白名单；统一密码错误语义；返回令牌对与用户摘要。
- `POST /auth/refresh`：白名单；完成一次性轮换；重放触发全会话撤销。
- `POST /auth/logout`：需访问令牌；幂等；返回 `data: null`。
- `GET /auth/me`：需访问令牌；返回身份、成员摘要、状态与权限码。
- `GET /admin/users`：系统管理员；安全分页与白名单排序；软删除过滤；手机号脱敏。
- `POST /admin/users`：系统管理员；幂等；单条同步创建；批量返回 202 与异步受理。
- `PATCH /admin/users/{userId}`：系统管理员；幂等；状态或角色变更；禁用触发会话与通知撤销；写审计。
- `GET /admin/permissions`：系统管理员；只读矩阵与筛选。
- `GET /admin/user-quotas/{userId}`：系统管理员；返回数据库字段命名的上限与用量。
- `PATCH /admin/user-quotas/{userId}`：系统管理员；幂等；仅调整上限。
- C10 裁决：模型与领域层使用数据库字段名；序列化层按接口文档输出别名。

## 外部交互

- membership 服务：查询 `membership_id`、`membership_status` 与 `unverified_start_policy`。
- workspace 服务：通过事件撤销活动工作区会话，不直接更新其表。
- notification 服务：通过事件标记已读并停止推送。
- file/storage 服务：读取批量导入 CSV 对象；不直接操作文件表。
- M3 编排：通过 `adjust_quota(user_id, delta, idempotency_key)` 使用行级锁与幂等记录执行原子调整。

## 技术决策

- 密码哈希使用 Django 密码哈希器；禁止在日志、审计和响应中出现密码或令牌。
- 写接口统一挂 common 幂等装饰器；认证失败与权限拒绝同样落审计。
- 批量导入幂等以同一请求摘要与幂等键判断，重复提交回放原受理响应。
- 配额调整在事务内先写业务事实与幂等标记，再发布 Outbox 事件；事务失败整体回滚。
- 所有查询默认过滤软删除用户，除非明确需要后台恢复场景。

## 测试策略

- 单元测试：密码哈希、令牌轮换、重放检测、脱敏、范围解析、配额原子性。
- API 测试：认证接口、错误码、管理接口、幂等与审计。
- 权限矩阵测试：四种角色逐条断言，覆盖直接构造他人资源 ID。
- 并发测试：同一幂等键重复调用与并发扣减不越限。
- 集成测试：外部领域服务模拟、Outbox 事件、Celery 批量导入。
- 质量门槛：identity 覆盖率不低于 80%，Ruff format/check 通过。
