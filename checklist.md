# M1-membership 验收清单 Checklist

## 状态：已完成并通过本机质量门禁

## 一、行为检查

### 状态机

| 检查项 | 期望 |
| --- | --- |
| 用户申请 | 创建 `PENDING`，来源 `APPLY`，记录申请时间 |
| 重新申请 | `REJECTED/EXITED/REMOVED -> PENDING`，不覆盖历史事实 |
| 审核通过 | `PENDING -> ACTIVE`，记录审核人与时间 |
| 审核拒绝 | `PENDING -> REJECTED`，拒绝备注必填 |
| 主动退出 | `ACTIVE -> EXITED`，记录退出时间与原因 |
| 管理员移除 | `ACTIVE -> REMOVED`，记录移除时间与原因 |
| 非法转移 | 返回 `STATE_CONFLICT`，数据库状态不变 |
| 状态留痕 | 每次成功转移记录 `previous_status` |

### 用户端接口

| 检查项 | 期望 |
| --- | --- |
| 查询自身记录 | 只返回当前用户自己的成员记录 |
| 伪造用户过滤 | 无法查看他人成员记录 |
| 状态过滤 | 仅接受五种合法成员状态 |
| 分页契约 | 返回 `data.items/page/page_size/total/request_id` |
| 申请字段 | `message` 不超过 500 字符 |
| 退出字段 | `reason` 不超过 200 字符 |
| 申请通知 | 申请成功后管理员收到申请事件 |
| 阻断退出 | 返回具体阻断事项而非笼统错误 |

### 教学端接口

| 检查项 | 期望 |
| --- | --- |
| 成员列表 | 支持分页、状态多选、关键词搜索 |
| 申请列表 | 仅返回申请来源且 `PENDING`，最早优先 |
| 已拒绝追溯 | `status=REJECTED` 可查询 |
| 审核幂等 | 同一 `Idempotency-Key` 重放原状态与响应体 |
| 直接添加 | 目标用户存在、ACTIVE、未删除 |
| 移除成员 | 历史任务保留，不级联删除 |
| 最后管理员 | 并发移除只允许一次成功，其余 40905 |
| 敏感信息 | 手机号与邮箱对外脱敏 |
| ORG_SUB_ADMIN | 仅可见授权范围内成员，C8 下不可写 |

## 二、集成检查

### identity 接缝

| 检查项 | 期望 |
| --- | --- |
| provider 配置 | `IDENTITY_MEMBERSHIP_PROVIDER` 指向 membership 实现 |
| 登录响应 | membership status 出现在用户摘要中 |
| `/me` 响应 | membership status 与当前数据库状态一致 |
| 无成员记录 | `get_membership` 返回 `None` |
| 未实名策略 | 返回 `DENIED/READ_ONLY/ALLOWED` |
| 会话撤销 | 只发布 Outbox 事件，不访问 M4-B 表或 Redis |
| identity 回归 | identity 全量测试通过 |

### 跨模块协作

| 检查项 | 期望 |
| --- | --- |
| 任务发布快照 | `get_active_membership_id()` 返回当前活动成员 ID |
| 启动实时校验 | 快照存在但成员已失效时，`is_active_member()` 为 false |
| 启动断言 | 非 ACTIVE 成员返回对应成员错误 |
| 阻断查询 | 只通过只读接缝获取其他模块事实 |
| 事件消费 | M4-B 可按 `event_id` 消费会话撤销事件 |

## 三、数据与安全检查

| 检查项 | 期望 |
| --- | --- |
| 表结构 | 与数据库 V4.0 快照一致 |
| Django 模型 | `managed = False` |
| migration | 未新增任何 migration |
| DDL | 未执行或生成任何 DDL |
| 唯一成员 | 同一用户无并存 PENDING/ACTIVE 记录 |
| 越权防护 | 服务层独立校验角色与数据范围 |
| 审计 | 每个写操作记录 request/trace ID 与业务对象 |
| 脱敏 | 审计、日志、响应无明文凭据 |
| 错误码 | 只使用 common 已登记错误码 |
| 依赖 | 未新增三方依赖 |

## 四、并发与幂等检查

| 检查项 | 期望 |
| --- | --- |
| 重复申请并发 | 只产生一条申请事实 |
| 审核并发 | 只有一次审核成功，其余返回状态或阻断错误 |
| 审核幂等重放 | 同 key 同摘要返回原响应 |
| 幂等冲突 | 同 key 不同摘要返回 40902 |
| 退出并发 | 多次退出只成功一次 |
| 移除并发 | 多次移除只成功一次 |
| 最后管理员并发 | 仅一个成功，其余 40905 |
| 事件去重 | 同一业务事实仅发布一次 Outbox 事件 |
| SSE 预备 | 事件均含稳定 `event_id` |

## 五、质量门禁

### 命令

```powershell
Set-Location agent
uv run ruff format --check backend
uv run ruff check backend
uv run pytest backend/apps/membership -q --cov=apps.membership --cov-report=term-missing
uv run pytest backend/apps/identity -q
uv run python backend/manage.py check --settings=config.settings.test
```

### 通过标准

| 检查项 | 期望 |
| --- | --- |
| 格式 | `ruff format --check` 通过 |
| 静态检查 | `ruff check` 通过 |
| membership 测试 | 全部通过 |
| identity 回归 | 全部通过 |
| Django check | 无错误 |
| 覆盖率 | `apps.membership` 不低于 80% |
| 冒烟 | 种子环境可执行申请、审核、退出、移除链路 |
| 追踪 | 成功或失败均可按 request/trace ID 查询 |

## 六、未决冲突记录

| 编号 | 当前保守策略 | 需确认事项 |
| --- | --- | --- |
| C8 | ORG_SUB_ADMIN 只读，不可审核/添加/移除 | 是否拥有审核权 |
| C9 | 存储 `APPLY/DIRECT/IMPORT`，映射集中一处 | 对外枚举是否需要变更 |
| C11 | 以数据库 BIGINT 主键为准 | 是否引入业务可读 ID |
| C12 | 使用 `MEMBERSHIP_CHANGE_BLOCKED` | 重复申请与阻断错误语义 |
| C13 | 使用 `LAST_TEAM_ADMIN_PROTECTED` | 最后管理员保护错误码 |

## 七、验收结论

| 项目 | 结论 |
| --- | --- |
| 行为检查 | 通过；状态机、用户端、教学端、阻断与事件测试通过 |
| 集成检查 | 通过；identity provider 接缝与 identity 全量回归通过 |
| 数据与安全检查 | 通过；无 migration/DDL/新依赖，角色校验、脱敏与审计测试通过 |
| 并发与幂等检查 | 通过；重复申请、重复审核、并发审核、幂等重放与事件去重测试通过 |
| 质量门禁 | 通过；membership 31 passed、coverage 86%、identity 14 passed、Django check 无错误、ruff format/check 通过 |

## 八、验证记录

| 时间 | 命令 | 结果 |
| --- | --- | --- |
| 2026-09-18 10:49 | `ruff format --check apps/membership config` | 34 files already formatted |
| 2026-09-18 10:49 | `ruff check apps/membership config` | All checks passed |
| 2026-09-18 10:50 | `pytest apps/membership -q --cov=apps.membership --cov-report=term-missing` | 31 passed, coverage 86% |
| 2026-09-18 10:50 | `pytest apps/identity -q` | 14 passed |
| 2026-09-18 10:51 | `manage.py check --settings=config.settings.test` | 0 issues |
