# 02 后端应用结构与 API 契约

> 上游：`00_架构总纲.md`、`01_领域模型与数据设计.md`  
> 状态：目标后端设计，尚未实施

## 一、工程结构

```text
backend/education_experiment_platform/
├─ education_experiment_platform/
│  ├─ settings/{base,local,test,integration,prod}.py
│  ├─ api_urls.py
│  ├─ celery.py
│  └─ asgi.py
└─ apps/
   ├─ core/
   ├─ accounts/
   ├─ courses/
   ├─ labtemplates/
   ├─ experiments/
   ├─ provisioning/
   ├─ workspaces/
   ├─ reports/
   ├─ reviews/
   ├─ archives/
   ├─ agents/
   ├─ governance/
   ├─ notifications/
   ├─ analytics/
   └─ integrations/
```

每个业务 app 采用统一布局：

```text
models.py           数据结构和本地不变量
services.py         写用例、事务、状态跃迁、审计和 Outbox
selectors.py        按 actor/portal/course 裁剪的读模型
permissions.py      接口级粗粒度准入
serializers.py      输入校验和响应结构
views.py            HTTP 到 service/selector 的薄适配
urls.py             app 路由
events.py           事件名与载荷构造
tasks.py            Celery 入口，只调用 service/port
ports.py            外部依赖 Protocol
adapters/           端口实现
tests/              模型、service、API、权限和并发测试
```

禁止从 View、Serializer 或 Celery task 直接 `model.save(status=...)` 推进业务状态。跨 app 读走 selector，写走 service；避免通过导入他域模型拼接隐含规则。

## 二、门户识别与认证

### 2.1 网关到应用

三个站点将本站 `/api/v2/*` 反向代理到共享 Django。网关根据已匹配的 Host 覆盖写入可信头：

```text
user.example.edu    → X-Portal: USER
teacher.example.edu → X-Portal: TEACHING
admin.example.edu   → X-Portal: PLATFORM
```

网关必须丢弃浏览器传入的同名头。Django `PortalContextMiddleware` 只接受受信代理来源，并把 portal 写入 request context、审计和 trace。未识别 Host/portal 返回 400，不猜测默认端。

机器客户端使用独立 `api.example.edu`。Gateway 只允许该 Host 访问 `/api/v2/integrations/oauth/token` 和 `/api/v2/integrations/open/*`，删除外部传入的 `X-Portal`、`X-Auth-Context` 和 client/scope 头，再写入可信 `X-Auth-Context: INTEGRATION`。Django 对 token 路由校验 client credential，对 open 路由校验短期 access token 并创建 `IntegrationPrincipal`；它不是 Portal 用户，也不能访问 `/me`、`/teaching` 或 `/platform`。

`PortalContextMiddleware` 仅对三端浏览器命名空间要求 portal；`IntegrationContextMiddleware` 仅对上述机器路由生效。两类上下文互斥，未知 Host、上下文和路由组合一律返回 400/403。

入口是两层代理时，职责固定如下：

```text
Nginx：TLS、静态站点、Host 路由、请求体限制、SSE/WS 代理
  → API Gateway：/api/v2 路由、限流、熔断、超时、版本、trace 透传
    → Django：Session/CSRF、对象权限、状态机和业务事实
```

API Gateway 可以做身份存在性预检查，但不能缓存课程、选课、任务或审核权限作为最终结论。业务授权每次由 Django selector/service 依据 MySQL 事实重新判断。网关重试只允许 GET/HEAD 和明确幂等的请求；写请求默认不重试。

### 2.2 Session

- Session/CSRF Cookie 为 host-only，不设置 `.example.edu` 父域。
- Session 数据包含 `user_id`、`portal`、认证时间和安全版本。
- 请求 portal 与 Session portal 不一致时返回 401 并撤销该 Session。
- 教师端登录要求有效教师资格；管理端登录要求有效管理员资格。
- 密码变更、账号停用和安全事件撤销所有 portal Session。
- 教师/管理员以学生身份操作时另行登录用户端，不允许在单页面切换 portal。

### 2.3 门户准入不等于对象权限

```text
登录成功
  → portal 准入
  → 全局资格（教师/管理员）
  → 课程任职或选课
  → 资源所属课程/本人关系
  → 当前状态和时间窗口
```

任一层失败即拒绝。前端 `eligible_portals` 只用于展示跨站链接，不是后端授权依据。

## 三、权限矩阵

图例：`✓` 允许，`本` 仅本人，`课` 仅有本课程授权，`监` 受控监管只读，`✗` 禁止。

| 能力 | 用户端学生 | 课程负责人 | 授权助教 | 平台管理员 |
|---|---:|---:|---:|---:|
| 登录对应站点 | ✓ | ✓ | ✓ | ✓ |
| 浏览公开课程/申请选课 | 本 | 可另登用户端 | 可另登用户端 | 监 |
| 查看/退出本人选课 | 本 | ✗ | ✗ | 监 |
| 创建课程 | ✗ | ✓ | ✗ | ✗ |
| 编辑/发布/关闭课程 | ✗ | 课 | ✗ | 冻结/下架异常处置 |
| 管理课程任职 | ✗ | 课 | ✗ | 监 |
| 审批选课/管理名册 | ✗ | 课 | 课（需 grant） | 监，不代审批 |
| 创建模板/版本/预检 | ✗ | 课 | 课（需 grant） | 运行预检监管 |
| 发布课程实验 | ✗ | 课 | 课（需 grant） | ✗ |
| 启动实验/进入工作区 | 本 | 仅另有选课时在用户端 | 同左 | ✗ |
| 保存/提交报告 | 本 | ✗ | ✗ | ✗ |
| 查看课程过程 | 本人任务 | 课 | 课（需 grant） | 监 |
| 作出审核结论 | ✗ | 课 | 课（需 grant） | **✗** |
| 导出课程成果 | 本人受控导出 | 课 | 课（需 grant） | 异常/合规导出 |
| 手动销毁实例 | ✗ | ✗ | ✗ | 异常处置，必须原因+审计 |
| 管理运行时/配额/安全 | ✗ | 查看本课程用量 | 查看授权范围 | ✓ |
| 维护章节/资料/公告/日历 | ✗ | 课 | 课（需 grant） | 监，不代编辑 |
| 课程问答 | 本课程提问/本人内容 | 课内回复/管理 | 课（需 grant） | 合规处置 |
| 延期/补交决定 | 仅申请 | 课 | 课（需 grant） | 监，不代决定 |
| 配置课程 Agent/知识库 | 使用 | 课 | 课（需 grant） | 平台策略与模型治理 |
| 查看分析 | 本人解释性建议 | 本课程 | 授权范围 | 平台/资源/质量汇总 |

硬规则：平台管理员不得通过管理端成为审核决定人；课程负责人也不能操作学生工作区；助教无 grant 时默认什么都看不到。

## 四、权限实现

### 4.1 接口级准入

接口权限类只做粗粒度检查：

```text
IsUserPortal
IsTeachingPortal + HasActiveTeacherQualification
IsPlatformPortal + HasActivePlatformAdminAssignment
```

不得在权限类中查询并缓存“所有可见课程”作为长生命周期事实；对象查询交给 selector。

### 4.2 数据级裁剪

每个资源提供 `visible_*` selector：

```python
visible_courses(actor, portal)
visible_enrollments(actor, portal, course_id=None)
visible_publications(actor, portal, course_id=None)
visible_tasks(actor, portal, course_id=None)
visible_reviews(actor, portal, course_id=None)
```

用户端只返回本人数据；教师端通过有效 `CourseStaff` + 未过期 grant 裁剪；管理端按监管策略只读全局数据。详情端点先用 selector 过滤再按 public_id 获取，不可见对象统一 404。

### 4.3 写服务再次校验

selector 结果不能代替写时检查。service 在事务内锁定聚合根，重新验证账号/资格、课程任职、grant、选课、状态、窗口和 row_version，以处理读写间状态变化。

## 五、服务层用例

### accounts

```text
grant_teacher_qualification
suspend_teacher_qualification
revoke_teacher_qualification
grant_platform_admin
revoke_platform_admin
disable_account_and_revoke_access
```

### courses

```text
create_course / update_course / publish_course / close_course / archive_course
transfer_course_ownership
appoint_course_assistant / grant_course_capability / revoke_course_staff
apply_for_course / withdraw_application / review_enrollment
drop_enrollment / remove_enrollment
create_chapter / publish_chapter / withdraw_chapter
create_material_version / publish_material_version / withdraw_material_version
publish_announcement / schedule_calendar_event
create_question / answer_question / moderate_course_qa
create_invitation / precheck_enrollment_import / execute_enrollment_import
clone_course / set_course_prerequisite / set_chapter_prerequisite
```

### labtemplates / experiments

```text
create_template / create_template_version / run_precheck / publish_version
create_publication / publish_experiment / close_publication / withdraw_publication
assign_tasks_for_publication / assign_task_for_late_enrollment
transition_task / start_task / submit_task / expire_task
request_task_extension / decide_task_extension
```

### workspaces / reviews / agents

```text
create_checkpoint / restore_checkpoint / append_operation_event
create_rubric_version / publish_rubric_version / score_review_criteria / add_review_annotation_revision
run_auto_check / run_similarity_check / decide_review
create_course_agent_profile / ingest_knowledge_source / publish_prompt_version
create_agent_session / retrieve_with_citations / request_tool / decide_tool_call
run_agent_eval_suite / submit_agent_feedback
```

### analytics / integrations

```text
rebuild_course_analytics / evaluate_risk_signals / generate_learning_recommendations
aggregate_resource_cost / calculate_course_quality
configure_oidc_provider / create_api_client / rotate_client_secret
register_webhook / replay_webhook_delivery / revoke_integration
```

每个写服务统一完成：认证 → Portal/Integration 准入与对象 scope → 幂等记录查询/同请求重放 → 状态与 If-Match/CAS → 行锁 → 业务写入 → 追加事实 → Audit → Outbox。已完成请求的精确重放在权限校验后、可变状态校验前返回原响应；新请求才执行状态和并发检查。外部 I/O 仅在事务提交后入队。

## 六、关键事务边界

| 用例 | 同一事务内必须完成 |
|---|---|
| 开放选课 | 锁课程、容量检查、建立 ACTIVE enrollment、事件、审计、Outbox |
| 审批通过 | 锁申请/课程、重新检查容量、转 ACTIVE、事件、Outbox |
| 负责人交接 | 锁课程与两名 staff、旧 OWNER 撤销、新 OWNER 生效、course.owner 更新、审计 |
| 发布实验 | 锁课程/版本、创建发布和受众事实、批量任务、跃迁、Outbox |
| 晚选课补建 | 锁 enrollment/publication、检查策略、幂等创建 task、事件 |
| 启动实验 | 锁 task、校验选课/窗口/配额、转 PROVISIONING、创建 job/预留、Outbox |
| 审核决定 | 锁 review/task、校验课程审核权、追加 decision、推进 task、Outbox |
| 退课/移除 | 锁 enrollment、重查 blockers、结束选课、撤销相关授权、Outbox |

禁止把 Docker/MinIO/模型 API 调用放在数据库事务中。

## 七、API 通用契约

| 项 | 规则 |
|---|---|
| 前缀 | `/api/v2/`；这是本项目首个正式 API，不提供旧 v1 兼容层 |
| 认证 | 三端使用 Portal 绑定的 Django Session + CSRF；机器 API 使用 IntegrationPrincipal |
| 标识 | public_id/业务 code，不接受自增主键 |
| 时间 | ISO 8601 带时区；数据库存 UTC |
| 分页 | `page/page_size`，最大 100；审计/事件用 cursor |
| 并发 | Versioned 资源 GET 返回 `ETag`；PATCH/PUT 和对现有聚合执行状态跃迁的 POST 要求 `If-Match` |
| 幂等 | 所有有副作用 POST 要求 `Idempotency-Key`；仅 `/auth/login`、`/auth/logout`、`/auth/logout-all`、`/integrations/oauth/token` 和无副作用的 `/course-invitations/resolve` 例外 |
| 异步 | `202 Accepted` + job + `Location` + events_channel + trace_id |
| 错误 | 统一信封，稳定 code、message、detail、trace_id、retryable |
| 缓存 | 身份/权限/任务响应 `private, no-store`；公开课程目录可短缓存 |

### 7.1 网关转发约束

| 路由 | Nginx/Gateway 要求 | Django 要求 |
|---|---|---|
| `/api/v2/*` | 无公共缓存；透传 `trace_id`、`X-Request-ID`；上传大小和超时受控 | 统一错误、Session/CSRF、对象 scope |
| `/api/v2/events/stream` | 关闭 buffering，长读超时，禁止重试 | Last-Event-ID、portal/scope 校验、事件去重 |
| `/workspace/*` | WebSocket Upgrade、短期连接、禁止公共缓存 | 校验工作区票据 hash/jti、task/student/instance scope |
| `/files/*` | 不暴露对象存储地址；下载限速和超时 | 每次校验 grant、次数、过期和课程范围 |
| `api.example.edu/api/v2/integrations/*` | 仅 token/open 路由；独立限流；覆盖 Integration auth context | client credential/access token、scope、resource grant、审计 |

网关只从 Host 映射 portal，不接受客户端自定义 `X-Portal`。Gateway、Django 和 Worker 使用同一个 W3C trace context，便于把入口请求串到异步作业和 MongoDB 日志。

### 路由视角

```text
/api/v2/auth/*             三站点公共认证入口，按 X-Portal 判准入
/api/v2/me/*               当前账号/用户端本人资源
/api/v2/courses/*          用户端公开课程目录
/api/v2/tasks/*            当前 actor 可见任务，仍按 portal 裁剪
/api/v2/teaching/*         教师端
/api/v2/platform/*         管理端
/api/v2/events/stream      portal/object scope SSE
/api/v2/auth/oidc/*        三站点 OIDC 登录/回调，仍绑定目标 portal
/api/v2/platform/integrations/*  管理端 OIDC/API Client/Webhook 配置
/api/v2/integrations/oauth/token 机器客户端 token
/api/v2/integrations/open/*      scope 化开放 API
```

开放 API 使用独立 client credential/OIDC access token，仅允许显式 scope；浏览器三端继续使用 Session + CSRF。开放 API 和 Webhook 复用同一 service/selector，不得通过 integration 绕过 portal 对象权限。首期不提供 Moodle/Canvas/LTI 专用路由。

三个网页的页面 URL 不使用这些前缀；API 路由分区和前端网站路由是两个概念。

## 八、错误码

| HTTP | 代码示例 |
|---|---|
| 400 | `VALIDATION_ERROR`、`PORTAL_UNKNOWN` |
| 401 | `AUTH_REQUIRED`、`SESSION_PORTAL_MISMATCH`、`SESSION_REAUTH_REQUIRED` |
| 403 | `PORTAL_ACCESS_DENIED`、`TEACHER_QUALIFICATION_REQUIRED`、`ENROLLMENT_NOT_ACTIVE`、`COURSE_GRANT_REQUIRED` |
| 404 | `RESOURCE_NOT_FOUND`（包含不可见资源） |
| 409 | `COURSE_STATE_CONFLICT`、`ENROLLMENT_CAPACITY_FULL`、`ENROLLMENT_BLOCKED`、`TASK_STATE_CONFLICT`、`QUOTA_EXCEEDED` |
| 412 | `ROW_VERSION_CONFLICT` |
| 422 | `IDEMPOTENCY_KEY_REUSED`、`IMMUTABLE_VERSION`、`CROSS_COURSE_REFERENCE` |
| 428 | `PRECONDITION_REQUIRED` |
| 429 | `RATE_LIMITED` |
| 503 | `RUNTIME_UNAVAILABLE`、`ADAPTER_DEGRADED` |

```json
{
  "error": {
    "code": "ENROLLMENT_CAPACITY_FULL",
    "message": "课程名额已满",
    "detail": {"course_id": "01..."},
    "trace_id": "4f9a2c1b7e3d6a80",
    "retryable": false
  }
}
```

## 九、OpenAPI 与契约冻结

- 后端导出唯一 `openapi.json`，采用 `08_API接口详细设计.md` 定义的功能级 tag；每个 operation 另标记允许的 portal 或 `INTEGRATION` auth context。
- `platform-integrations` 与 `external-api` 分离；三端应用不得导入 `external-api` token 能力，也不得把 client secret 打进前端制品。
- 前端共享包从规范生成，不手写响应类型。
- CI 对 OpenAPI 做 diff；删除/改类型属于破坏性变更。
- 三个网页独立发布，不能要求三个前端与后端在同一时刻原子发布。
- 同一 `/api/v2` 的滚动发布顺序为：先发布向后兼容的后端/网关扩展，再分别发布三端，最后在所有旧制品退出后清理已弃用字段；兼容窗口有明确截止时间和观测指标。
- 删除路径/字段、改变类型或语义等破坏性变更必须使用新 major base path（例如 `/api/v3`）或让新旧 revision 并存，不能在仍有旧前端运行时原地替换 `/api/v2`。
- “不提供旧 v1 兼容层”只针对本绿地项目之前的旧系统，不取消本项目自身滚动发布所需的短期契约兼容。
