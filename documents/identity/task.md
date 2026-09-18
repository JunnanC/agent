# identity 模块 Task

## 文件清单

- `agent/backend/apps/identity/__init__.py`
- `agent/backend/apps/identity/apps.py`
- `agent/backend/apps/identity/models.py`
- `agent/backend/apps/identity/selectors.py`
- `agent/backend/apps/identity/services/__init__.py`
- `agent/backend/apps/identity/services/auth.py`
- `agent/backend/apps/identity/services/admin_users.py`
- `agent/backend/apps/identity/services/permissions.py`
- `agent/backend/apps/identity/services/quotas.py`
- `agent/backend/apps/identity/serializers.py`
- `agent/backend/apps/identity/permissions.py`
- `agent/backend/apps/identity/views.py`
- `agent/backend/apps/identity/urls.py`
- `agent/backend/apps/identity/tasks.py`
- `agent/backend/apps/identity/tests/__init__.py`
- `agent/backend/apps/identity/tests/conftest.py`
- `agent/backend/apps/identity/tests/test_models.py`
- `agent/backend/apps/identity/tests/test_auth_api.py`
- `agent/backend/apps/identity/tests/test_permissions.py`
- `agent/backend/apps/identity/tests/test_admin_users_api.py`
- `agent/backend/apps/identity/tests/test_quotas.py`
- `agent/backend/config/settings/base.py`
- `agent/backend/config/urls.py`
- `agent/backend/README.md`

## 任务列表

### T1: 注册应用与模型映射

1. 创建 identity 应用与配置。
2. 按 V4.0 实现六张非托管模型，字段名不得变更。
3. 在测试设置中注册应用，不生成 migration。

验证：
- `manage.py check --settings=config.settings.test` 通过。
- 搜索 identity 目录无 `migrations`。

### T2: 选择器与序列化

1. 实现用户、角色、权限、认证状态与配额选择器。
2. 实现手机号与实名脱敏。
3. 实现管理列表筛选、白名单排序与软删除过滤。
4. 实现 C10 序列化别名映射。

验证：
- 模型单元测试覆盖字段边界、脱敏与排序。

### T3: 认证服务与 API

1. 实现登录、刷新、登出与当前用户查询。
2. 密码使用 Django 哈希器；错误密码与不存在账号返回一致语义。
3. 实现访问令牌签发、刷新令牌轮换与重放检测。
4. 登出幂等并撤销当前访问令牌与关联刷新令牌。

验证：
- 认证 API 测试覆盖成功、错误密码、不存在账号、禁用账号、无成员身份。
- 覆盖刷新轮换、旧令牌失效、重放触发全部认证会话撤销。
- 登出后访问令牌立即失效，重复登出成功。

### T4: 权限领域服务

1. 实现 `PrincipalPermissionProvider` 与 `AuditableActorProvider`。
2. 实现角色、权限码、数据范围与认证状态组合裁决。
3. 通过外部 membership 领域服务读取未认证启动策略。
4. 提供 DRF 权限类：认证、系统管理员、动作权限、数据范围。

验证：
- 四种角色权限矩阵逐条断言。
- 直接构造他人资源 ID 时返回 `403 FORBIDDEN`。
- 未认证且团队策略 `DENIED` 时启动实验动作被拒绝。

### T5: 管理用户 API

1. 实现系统管理员用户列表。
2. 实现单条创建与批量导入异步受理。
3. 创建用户时初始化默认配额。
4. 实现状态与角色变更，禁用用户时发布会话与通知撤销事件。
5. 所有写操作接入 common 幂等与审计。

验证：
- 列表分页、筛选、排序、脱敏与软删除过滤正确。
- 单条创建返回 201 并生成配额。
- 批量导入返回 202，重复提交不产生两批用户。
- 自身不可禁用或降级。
- 状态与角色变更写审计。

### T6: 权限矩阵 API

1. 实现系统管理员只读权限矩阵查询。
2. 支持 `role_code` 与 `resource` 筛选。
3. 保持字典只读，不提供修改入口。

验证：
- 返回四个内置角色、权限明细与统计。
- 非系统管理员访问返回 `403 FORBIDDEN`。

### T7: 配额服务与 API

1. 实现配额查询与上限调整。
2. 实现 `adjust_quota(user_id, delta, idempotency_key)`。
3. 事务内锁定配额行，先写事实与幂等标记，再发布 Outbox 事件。
4. 保持 `0 <= used_x <= max_x`。

验证：
- 查询返回上限与用量。
- 同一幂等键重复调用只生效一次。
- 并发扣减不超过上限。
- 事务回滚时事实、幂等标记与事件均回滚。

### T8: 集成与文档

1. 将 identity URL 挂载到全局路由。
2. 在 README 记录接口、令牌、权限模型与模块边界。
3. 确认 common 依赖只从公共模块导入。

验证：
- 全局 Django check 通过。
- README 与实际行为一致。
- identity 不导入其他业务应用模型。

### T9: 质量验收

1. 运行 Ruff format/check。
2. 运行 identity 测试与覆盖率。
3. 扫描日志、审计、响应与测试断言，确认无凭据明文。
4. 按 checklist 逐项验收并记录证据。

验证：
- `.venv/Scripts/python.exe -m ruff format --check apps/identity`
- `.venv/Scripts/python.exe -m ruff check apps/identity`
- `.venv/Scripts/python.exe -m pytest apps/identity -q --cov=apps.identity --cov-report=term-missing`
- 覆盖率不低于 80%。

## 执行顺序

T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9
