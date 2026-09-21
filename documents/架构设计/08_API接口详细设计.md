# 08 API 接口详细设计

> 上游：`00`～`07`  
> 状态：绿地（greenfield）v2 API 契约，尚未生成 OpenAPI/代码

## 一、统一约定

### 1.1 基础

| 项 | 约定 |
|---|---|
| Base path | `/api/v2`；本项目首个正式 API，不提供旧 v1 兼容层 |
| 站点 | 三个网页站点写可信 `X-Portal`；`api.*` 是无前端的机器 API 入口 |
| 认证 | 三端浏览器使用 host-only Django Session + CSRF；开放 API 使用 client credential/OIDC access token |
| Content-Type | `application/json`；文件用 multipart/受控下载 |
| 标识 | public_id/业务 code，不暴露自增主键 |
| 时间 | ISO 8601 带时区 |
| 分页 | `page`、`page_size<=100`；审计/事件用 cursor |
| 搜索排序 | `q`、白名单 filter、`ordering` |
| 并发 | Versioned 资源 GET 返回 ETag；PATCH/PUT 和状态跃迁 POST 使用 `If-Match` |
| 幂等 | 除明确列出的认证、token 和无副作用查询例外，所有有副作用 POST 使用 `Idempotency-Key` |
| Trace | 响应头和错误体包含 `trace_id` |

### 1.2 Portal

| Host | Auth context | API 主要分组 |
|---|---|---|
| `user.*` | Portal `USER` | public、me、tasks、reports、workspaces、agents |
| `teacher.*` | Portal `TEACHING` | teaching |
| `admin.*` | Portal `PLATFORM` | platform |
| `api.*` | `INTEGRATION` | integrations/oauth/token、integrations/open |

同一路径从错误 portal 调用返回 `403 PORTAL_ACCESS_DENIED`。`X-Portal` 不接受客户端自行指定。

非浏览器开放 API 只允许从 `api.*` 进入，不使用 `X-Portal` 模拟三端身份。Gateway 删除客户端传入的上下文头并写可信 `X-Auth-Context: INTEGRATION`；Django 验证 client credential/access token 后创建 IntegrationPrincipal，并复用相同的 service、selector、对象 scope、幂等和审计规则。

### 1.3 成功响应

详情：

```json
{
  "data": {"public_id": "01...", "status": "ACTIVE"},
  "meta": {"trace_id": "4f9a2c1b7e3d6a80"}
}
```

列表：

```json
{
  "data": [],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 0,
    "trace_id": "4f9a2c1b7e3d6a80"
  }
}
```

删除/撤销类操作仍返回更新后的资源或操作结果，避免客户端猜状态；没有响应体时使用 204。

### 1.4 异步响应

```http
202 Accepted
Location: /api/v2/jobs/01...
```

```json
{
  "data": {
    "job_id": "01...",
    "status": "QUEUED",
    "subject_id": "EXP-...",
    "events_channel": "task:EXP-..."
  },
  "meta": {"trace_id": "4f9a2c1b7e3d6a80"}
}
```

### 1.5 错误

```json
{
  "error": {
    "code": "COURSE_GRANT_REQUIRED",
    "message": "没有该课程的审核权限",
    "detail": {"course_id": "01...", "capability": "REVIEW_SUBMISSION"},
    "trace_id": "4f9a2c1b7e3d6a80",
    "retryable": false
  }
}
```

越权且会泄露对象存在性的详情查询返回 404；已知本人对象但状态不允许返回 403/409。

## 二、认证与当前账号

| 方法 | 路径 | Portal | 说明 |
|---|---|---|---|
| GET | `/auth/csrf` | 三端 | 下发本站 CSRF Cookie |
| POST | `/auth/login` | 三端 | 账号密码登录；按 Host/portal 检查准入 |
| POST | `/auth/logout` | 三端 | 仅撤销本站 Session |
| POST | `/auth/logout-all` | 三端 | 撤销本人所有 portal Session |
| GET | `/me` | 三端 | 当前账号、portal、eligible_portals、资格/课程 scope 摘要 |
| PATCH | `/me` | 三端 | 修改本人展示资料，要求 If-Match |
| POST | `/me/password` | 三端 | 修改密码并撤销其他 Session |
| GET/PUT | `/me/verification` | USER | 学校/企业身份资料 |
| GET | `/auth/oidc/{provider_key}/start` | 三端 | 发起允许该 portal 使用的 OIDC 登录，生成短期 state/nonce |
| GET | `/auth/oidc/{provider_key}/callback` | 三端 | 校验 issuer、state、nonce 和 PKCE 后建立本站 Session |
| GET | `/me/oidc-identities` | 三端 | 本人已绑定外部身份，只返回脱敏摘要 |
| POST | `/me/oidc-identities/{id}/unlink` | 三端 | 近期认证后解绑，必须保留至少一种可登录方式 |

登录请求不接收 portal 字段，portal 来自可信 Host。教师端无有效资格返回 `403 TEACHER_QUALIFICATION_REQUIRED`；管理端无管理员资格返回 `403 PLATFORM_ACCESS_REQUIRED`。

`GET /me` 示例：

```json
{
  "data": {
    "public_id": "01...",
    "display_name": "张同学",
    "portal": "USER",
    "eligible_portals": ["USER"],
    "account_status": "ACTIVE",
    "permissions": ["course.catalog.view", "enrollment.apply"],
    "course_scopes": []
  },
  "meta": {"trace_id": "..."}
}
```

## 三、用户端课程与选课

### 3.1 课程目录

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/courses` | 公开课程；`q,status,enrollment_open,ordering,page` |
| GET | `/courses/{course_id}` | 公开详情、教师摘要、报名窗口、容量状态、实验摘要 |
| POST | `/course-invitations/resolve` | 无副作用且严格限流；校验邀请码后返回 UNLISTED 课程最小报名摘要，不回显邀请码 |

不返回名册、其他学生进度、内部配额和教师私有备注。`UNLISTED` 不出现在目录；详情只对已有 PENDING/ACTIVE enrollment 的本人可见。未选课用户先通过邀请码 resolve 获得最小摘要，再把原邀请码提交给选课接口；resolve 结果本身不授予课程访问权。

### 3.2 本人选课

| 方法 | 路径 | 幂等 | 说明 |
|---|---|---:|---|
| GET | `/me/enrollments` | - | 本人所有选课周期；按 status/course 分页 |
| GET | `/me/enrollments/{id}` | - | 本人选课详情和事件时间线 |
| POST | `/courses/{course_id}/enrollments` | 必需 | OPEN 直接 ACTIVE；APPROVAL 创建 PENDING |
| POST | `/me/enrollments/{id}/withdraw` | 必需 | 撤回 PENDING 申请 |
| GET | `/me/enrollments/{id}/drop-check` | - | 无副作用阻断检查，`Cache-Control: no-store` |
| POST | `/me/enrollments/{id}/drop` | 必需 | 事务内重查后退课 |

选课请求：

```json
{"application_message": "希望参加本课程"}
```

选课响应包括 `status`、`cycle_no`、课程摘要和是否会补建现有实验。容量冲突返回 409，重复 live enrollment 返回 `ENROLLMENT_ALREADY_LIVE`。

邀请码只通过选课请求的可选 `invitation_code` 提交；服务端保存和比对摘要，不在列表、日志或分析接口返回明文。邀请码不能绕过账号状态、课程状态、先修条件、容量和重复选课约束。

阻断响应：

```json
{
  "data": {
    "allowed": false,
    "blockers": [
      {"type": "UNFINISHED_TASK", "count": 2, "refs": ["EXP-..."], "message": "存在未完成实验"}
    ]
  },
  "meta": {"trace_id": "..."}
}
```

### 3.3 课程内容、问答与学习建议

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/courses/{course_id}/chapters` | 本课程可见章节树、完成要求和已满足的先修状态 |
| GET | `/courses/{course_id}/materials` | 已发布且当前学生可访问的课程资料，可按 chapter/type 查询 |
| GET | `/courses/{course_id}/announcements` | 已发布公告，按发布时间倒序 |
| GET | `/courses/{course_id}/calendar` | 课程窗口、实验截止时间和课程事件；支持时间范围过滤 |
| GET | `/courses/{course_id}/questions` | 课程问答；不返回隐藏、待处置或越权内容 |
| POST | `/courses/{course_id}/questions` | ACTIVE 学生提问，Idempotency-Key 必需 |
| POST | `/questions/{question_id}/answers` | ACTIVE 学生按课程策略回复，Idempotency-Key 必需；教师使用 teaching 路由 |
| GET | `/me/recommendations` | 本人的解释性学习建议、依据和失效时间 |

课程内容详情不得暴露 MinIO key；资料下载仍通过 download grant。学习建议只提供可解释的下一步候选，不能自动选课、提交实验、申请延期或改变任务状态。

## 四、用户端实验

| 方法 | 路径 | 幂等 | 说明 |
|---|---|---:|---|
| GET | `/me/dashboard` | - | 我的课程/实验统计和下一步 |
| GET | `/tasks` | - | USER portal 只返回本人；`course,status,runtime_type,q` |
| GET | `/tasks/{task_id}` | - | 详情、课程、冻结环境、允许动作 |
| GET | `/tasks/{task_id}/transitions` | - | 本人任务时间线 |
| POST | `/tasks/{task_id}/start` | 必需 | ASSIGNED → PROVISIONING，返回 202 阶段骨架 |
| POST | `/tasks/{task_id}/enter` | 必需 | READY → IN_PROGRESS，并签发工作区会话 |
| POST | `/tasks/{task_id}/complete` | 必需 | 非报告任务提交系统成果 |
| GET | `/tasks/{task_id}/provisioning-job` | - | 装载状态和阶段 |
| POST | `/tasks/{task_id}/retry` | 必需 | 仅 retryable FAILED |
| GET | `/tasks/{task_id}/extensions` | - | 本人查看延期/补交申请及决定历史 |
| POST | `/tasks/{task_id}/extension-requests` | 必需 | 提交延期/补交申请；不直接改变原发布窗口 |

任务详情 `allowed_actions` 由服务端按状态计算，前端不自造：

```json
{
  "data": {
    "public_id": "EXP-202609-000137",
    "course": {"public_id": "01...", "title": "AI 实践"},
    "status": "READY",
    "allowed_actions": ["ENTER"],
    "environment": {
      "runtime_type": "CONTAINER",
      "image_display": "python:3.13",
      "resource": {"cpu_cores": 2, "memory_mb": 4096, "disk_gb": 20},
      "workspace_capabilities": {"webide": true, "terminal": true},
      "editable": false
    },
    "row_version": 4
  },
  "meta": {"trace_id": "..."}
}
```

## 五、工作区、报告、Agent 与结果

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/tasks/{id}/workspace-sessions` | USER，本人；短期票据，要求 Idempotency-Key |
| POST | `/workspace-sessions/{id}/renew` | 重验选课/task/instance 后续签 |
| POST | `/workspace-sessions/{id}/revoke` | 本人主动退出 |
| PUT | `/tasks/{id}/workspace-snapshot` | 自动保存，`client_seq` 幂等/单调 |
| GET/PUT | `/tasks/{id}/report-draft` | 本人草稿；PUT 使用 If-Match |
| POST | `/tasks/{id}/attachments` | 扫描后登记附件 |
| POST | `/tasks/{id}/submit-report` | 冻结版本，Idempotency-Key 必需 |
| GET | `/tasks/{id}/report-versions` | 本人历史提交只读 |
| GET | `/tasks/{id}/review-result` | 审核反馈与允许动作 |
| GET | `/tasks/{id}/archive` | 归档/销毁结果 |
| GET | `/tasks/{id}/checkpoints` | 本人检查点列表和当前工作区版本 |
| POST | `/tasks/{id}/checkpoints` | 从当前工作区版本创建不可变检查点，幂等 |
| POST | `/tasks/{id}/checkpoints/{checkpoint_id}/restore` | 恢复为新的工作区版本，不覆盖历史，幂等+If-Match |
| GET | `/tasks/{id}/operation-replay` | cursor 分页返回本人可见的受控操作时间线和脱敏结果 |
| GET | `/courses/{id}/agent-profile` | 当前学生可用的模式、能力和限制摘要 |
| POST | `/courses/{id}/agent-sessions` | 创建 `KNOWLEDGE_QA` 课程问答会话，幂等 |
| POST | `/tasks/{id}/agent-sessions` | 为本人有效任务创建提示/诊断/报告/工作区会话，幂等 |
| GET | `/agent-sessions/{id}` | 本人会话、绑定的 profile/prompt/knowledge 版本和状态 |
| GET | `/agent-sessions/{id}/messages` | cursor 分页读取消息、引用和工具调用摘要 |
| POST | `/agent-sessions/{id}/messages` | 流式/异步推理，限流 |
| POST | `/agent-tool-calls/{id}/decide` | 本人批准/拒绝需用户确认的工具调用 |
| POST | `/agent-messages/{id}/feedback` | 本人提交有用/无用、问题类型和可选说明，幂等 |

用户端永远没有直接销毁实例接口。任务到期/撤回/审核通过后的回收由服务端编排。

`KNOWLEDGE_QA` 可只绑定课程；`SOCRATIC_HINT`、`DEBUG_ASSIST`、`REPORT_COACH`、`WORKSPACE_ASSIST` 必须绑定本人有效任务。知识问答的 assistant message 返回 `citation_status` 和 `citations[]`，每条引用包含 `source_version_id`、标题、受控片段和 download grant 入口。没有可靠来源时返回明确降级状态，禁止生成伪造引用。Agent 输出、反馈或工具结果都不能直接修改任务、报告提交、审核、实例或配额。

## 六、教师端课程

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET/POST | `/teaching/courses` | 有效教师；POST course.create | 我的课程/创建草稿 |
| GET/PATCH | `/teaching/courses/{id}` | 本课程 staff；PATCH OWNER | 详情/编辑，If-Match |
| POST | `/teaching/courses/{id}/publish` | OWNER | 发布课程，幂等+If-Match |
| POST | `/teaching/courses/{id}/close` | OWNER | 停止新选课/新实验 |
| GET | `/teaching/courses/{id}/archive-check` | OWNER | 归档阻断 |
| POST | `/teaching/courses/{id}/archive` | OWNER | 归档，只读化 |
| POST | `/teaching/courses/{id}/transfer-owner` | OWNER | 负责人交接，幂等+If-Match |

创建课程请求：

```json
{
  "code": "COURSE-2026-AI-001",
  "title": "AI 实践",
  "summary": "...",
  "visibility": "PUBLIC",
  "enrollment_mode": "APPROVAL",
  "capacity": 80,
  "enrollment_start": "2026-09-20T08:00:00+08:00",
  "enrollment_end": "2026-10-01T23:59:59+08:00",
  "teaching_start": "2026-10-08T08:00:00+08:00",
  "teaching_end": "2027-01-10T23:59:59+08:00"
}
```

### 教学团队

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/teaching/courses/{id}/staff` | OWNER 查询/任命助教 |
| PATCH | `/teaching/courses/{id}/staff/{staff_id}` | 更新状态，If-Match |
| GET/POST | `/teaching/courses/{id}/staff/{staff_id}/grants` | 固定能力授权 |
| POST | `/teaching/courses/{id}/staff/{staff_id}/revoke` | 撤销任职，阻断未交接职责 |

被任命者必须有有效教师资格。助教不能被授予 `OWNER`；负责人交接使用专用接口。

### 课程内容、复制与先修关系

| 方法 | 路径 | 权限/说明 |
|---|---|---|
| GET/POST | `/teaching/courses/{id}/chapters` | `MANAGE_CONTENT`；查询/创建章节 |
| GET/PATCH/DELETE | `/teaching/courses/{id}/chapters/{chapter_id}` | `MANAGE_CONTENT`；仅草稿结构可改，仅未引用草稿可删，要求 If-Match |
| POST | `/teaching/courses/{id}/chapters/{chapter_id}/publish` | 发布章节，幂等+If-Match |
| POST | `/teaching/courses/{id}/chapters/{chapter_id}/withdraw` | 撤下但保留历史引用，幂等+If-Match |
| GET/POST | `/teaching/courses/{id}/materials` | `MANAGE_CONTENT`；资料聚合列表/创建首个草稿版本 |
| GET/PATCH | `/teaching/courses/{id}/materials/{material_id}` | 编辑资料身份、章节归属和展示信息，If-Match |
| GET/POST | `/teaching/courses/{id}/materials/{material_id}/versions` | 版本列表/基于当前版本创建新草稿，POST 幂等 |
| GET/PATCH | `/teaching/courses/{id}/material-versions/{version_id}` | 查看/编辑 DRAFT 内容和资产，PATCH 要求 If-Match |
| POST | `/teaching/courses/{id}/material-versions/{version_id}/publish` | 冻结并发布为当前版本，幂等+If-Match |
| POST | `/teaching/courses/{id}/material-versions/{version_id}/withdraw` | 撤下版本但保留历史引用，幂等+If-Match |
| GET/POST | `/teaching/courses/{id}/announcements` | `MANAGE_CONTENT`；草稿列表/创建 |
| GET/PATCH | `/teaching/courses/{id}/announcements/{announcement_id}` | 编辑草稿，If-Match |
| POST | `/teaching/courses/{id}/announcements/{announcement_id}/publish` | 发布并创建通知投影，幂等+If-Match |
| GET/POST | `/teaching/courses/{id}/calendar-events` | `MANAGE_CONTENT`；查询/创建课程事件 |
| GET/PATCH/DELETE | `/teaching/courses/{id}/calendar-events/{event_id}` | 编辑/取消，If-Match |
| GET | `/teaching/courses/{id}/questions` | `MODERATE_QA`；含待处置问题 |
| POST | `/teaching/courses/{id}/questions/{question_id}/answers` | 教师答复，幂等 |
| POST | `/teaching/courses/{id}/questions/{question_id}/moderate` | 隐藏/恢复/锁定，原因必填，幂等+If-Match |
| GET/PUT | `/teaching/courses/{id}/prerequisites` | OWNER；课程先修关系，写入要求 If-Match 并校验无环 |
| GET/PUT | `/teaching/courses/{id}/chapters/{chapter_id}/prerequisites` | `MANAGE_CONTENT`；章节先修关系，写入要求 If-Match 并校验无环 |
| POST | `/teaching/courses/{id}/copy-jobs` | OWNER；选择可复制内容并异步创建新课程，幂等 |
| GET | `/teaching/courses/{id}/copy-jobs/{job_id}` | OWNER；查看逐项结果、错误和目标课程 |

课程复制只复制被选中的结构和配置，不复制名册、学生任务、报告、审核、Agent 会话、分析投影或运行实例。重试使用相同 idempotency key 时必须返回同一 job。

## 七、教师端名册

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/teaching/courses/{id}/enrollments` | OWNER/有 MANAGE_ENROLLMENT | 名册/申请列表 |
| GET | `/teaching/courses/{id}/enrollments/{eid}` | 同上 | 详情和历史 |
| POST | `/teaching/courses/{id}/enrollments/{eid}/review` | 同上 | APPROVE/REJECT；幂等+If-Match |
| GET | `/teaching/courses/{id}/enrollments/{eid}/removal-check` | 同上 | 移除阻断 |
| POST | `/teaching/courses/{id}/enrollments/{eid}/remove` | 同上 | 事务内重查并移除 |
| GET/POST | `/teaching/courses/{id}/invitations` | OWNER/有 MANAGE_ENROLLMENT | 查询脱敏邀请码/创建邀请码 |
| POST | `/teaching/courses/{id}/invitations/{invitation_id}/revoke` | 同上 | 撤销，幂等+If-Match |
| POST | `/teaching/courses/{id}/enrollment-imports/precheck` | 同上 | 上传 CSV 后逐行校验，返回 202 job |
| POST | `/teaching/courses/{id}/enrollment-imports/{job_id}/execute` | 同上 | 仅执行预检通过行，幂等+If-Match |
| GET | `/teaching/courses/{id}/enrollment-imports/{job_id}` | 同上 | 逐行状态、错误码和汇总，不回显敏感原文 |

审核请求：

```json
{"decision": "APPROVE", "note": "符合选课条件"}
```

审批时重新检查容量，不能信任列表加载时的剩余名额。

批量导入以 `job + row_no + normalized_identity` 保证逐行幂等；部分失败不回滚已成功行，重试只处理未成功行。导入不能绕过课程容量、重复 live enrollment、账号状态和先修规则。

## 八、教师端模板

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/teaching/courses/{cid}/templates` | 本课程模板列表/草稿 |
| GET/PATCH | `/teaching/courses/{cid}/templates/{id}` | 详情/编辑草稿 |
| GET/POST | `/teaching/courses/{cid}/templates/{id}/versions` | 版本列表/新草稿 |
| GET/PATCH | `/teaching/courses/{cid}/template-versions/{vid}` | 版本详情；仅 DRAFT 可改 |
| POST | `/teaching/courses/{cid}/template-versions/{vid}/precheck` | 202 预检 |
| GET | `/teaching/courses/{cid}/template-versions/{vid}/precheck-runs` | 历史 |
| POST | `/teaching/courses/{cid}/template-versions/{vid}/publish` | digest 一致后发布 |
| POST | `/teaching/courses/{cid}/template-versions/{vid}/withdraw` | 禁止新发布引用 |
| POST | `/teaching/courses/{cid}/template-versions/{vid}/clone` | 已发布版本修改的唯一入口 |
| POST | `/teaching/courses/{cid}/templates/{id}/assets` | 上传手册/资源/报告模板 |
| GET/PUT | `/teaching/courses/{cid}/template-versions/{vid}/auto-check-rules` | 自动检查规则草稿；发布模板时冻结规则版本，PUT 要求 If-Match |

课程 ID 不是装饰字段：模板/版本归属不一致返回 404/422，不能跨课程引用。

## 九、教师端实验发布与追踪

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/teaching/courses/{cid}/experiments` | 列表/创建发布草稿 |
| GET/PATCH | `/teaching/courses/{cid}/experiments/{pid}` | 详情/编辑草稿 |
| POST | `/teaching/courses/{cid}/experiments/{pid}/publish` | 冻结受众并分配；小批量 201，大批量进入 PUBLISHING 并返回 202 |
| POST | `/teaching/courses/{cid}/experiments/{pid}/close` | 停止晚选补建/新启动策略 |
| POST | `/teaching/courses/{cid}/experiments/{pid}/withdraw` | 撤回并编排已启动任务 |
| GET | `/teaching/courses/{cid}/experiments/{pid}/tasks` | 学生任务过程追踪 |
| GET | `/teaching/courses/{cid}/progress` | 课程汇总投影 |
| GET | `/teaching/courses/{cid}/extension-requests` | `MANAGE_EXTENSION`；按状态/实验/学生筛选 |
| GET | `/teaching/courses/{cid}/extension-requests/{request_id}` | 查看申请、原窗口和冲突摘要 |
| POST | `/teaching/courses/{cid}/extension-requests/{request_id}/decide` | 批准/拒绝并追加决定，幂等+If-Match |

创建/编辑请求：

```json
{
  "template_version_id": "01...",
  "title": "实验一：容器基础",
  "audience_mode": "ALL_ACTIVE",
  "selected_enrollment_ids": [],
  "late_enrollment_policy": "ASSIGN_UNTIL_DEADLINE",
  "assignment_deadline": "2026-10-20T23:59:59+08:00",
  "window_start": "2026-10-08T08:00:00+08:00",
  "window_end": "2026-10-31T23:59:59+08:00",
  "report_required": true,
  "rubric_version_id": "01...",
  "review_mode": "MANUAL_WITH_AUTO_CHECK"
}
```

`SELECTED` 的 enrollment 必须 ACTIVE 且属于该课程。发布后受众/模板/窗口核心语义不可静默改动；变更采用关闭/撤回和新发布。

延期批准生成个人 effective window 投影，保留 publication 原窗口和完整决定历史；不修改其他学生。决定时事务内重查任务状态、课程任职和最新版本，两个并发决定只有一个成功。

## 十、教师端审核与归档

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/teaching/courses/{cid}/reviews` | 本课程待审/历史，按授权裁剪 |
| GET | `/teaching/courses/{cid}/reviews/{rid}` | 报告、成果、自动检查和历史 |
| POST | `/teaching/courses/{cid}/reviews/{rid}/decide` | APPROVE/REJECT，只追加，幂等+If-Match |
| GET/POST | `/teaching/courses/{cid}/rubrics` | `REVIEW_SUBMISSION`；Rubric 列表/创建草稿 |
| GET/POST | `/teaching/courses/{cid}/rubrics/{rubric_id}/versions` | 版本列表/从现有版本 clone 草稿 |
| GET/PATCH | `/teaching/courses/{cid}/rubric-versions/{version_id}` | 编辑草稿及 criteria，If-Match |
| POST | `/teaching/courses/{cid}/rubric-versions/{version_id}/publish` | 发布不可变版本，幂等+If-Match |
| GET/PUT | `/teaching/courses/{cid}/reviews/{rid}/criterion-scores` | 按审核轮次保存 criterion 分值/说明，If-Match |
| GET/POST | `/teaching/courses/{cid}/reviews/{rid}/annotations` | 定位批注列表/追加批注，幂等 |
| POST | `/teaching/courses/{cid}/reviews/{rid}/annotations/{annotation_id}/revisions` | 仅作者在决定前追加修订，幂等+If-Match |
| POST | `/teaching/courses/{cid}/reviews/{rid}/annotations/{annotation_id}/revoke` | 追加撤销事实，不删除历史，幂等+If-Match |
| POST | `/teaching/courses/{cid}/similarity-runs` | 对指定成果集启动辅助相似度分析，返回 202，幂等 |
| GET | `/teaching/courses/{cid}/similarity-runs/{run_id}` | 算法/规则版本、覆盖范围和运行状态 |
| GET | `/teaching/courses/{cid}/similarity-runs/{run_id}/matches` | 候选匹配、证据片段和教师处置状态 |
| GET | `/teaching/courses/{cid}/archives` | 本课程归档列表 |
| GET | `/teaching/courses/{cid}/archives/{aid}` | 清单和校验 |
| POST | `/teaching/courses/{cid}/archives/{aid}/exports` | 申请课程成果受控导出 |

决定请求：

```json
{
  "decision": "REJECT",
  "score": null,
  "feedback": "请补充实验结果和错误分析"
}
```

平台管理员调用该决定接口始终拒绝，即使拥有全局监管权限。

publication 必须绑定已发布 `rubric_version_id`，审核轮次沿用该冻结版本并保存各 criterion 分值快照。`MANUAL_WITH_AUTO_CHECK` 只增加自动检查证据，最终 APPROVE/REJECT 仍必须由有权限教师作出。相似度结果只能作为教师辅助信号，不能自动拒绝、扣分、改变审核结论或任务状态。

## 十一、管理端账号和资格

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/platform/users` | 用户列表/创建账号 |
| GET/PATCH | `/platform/users/{id}` | 详情/停用恢复，If-Match |
| POST | `/platform/users/{id}/revoke-sessions` | 撤销所有门户会话 |
| GET | `/platform/teacher-qualifications` | 教师资格列表 |
| POST | `/platform/users/{id}/teacher-qualification` | 授予，幂等 |
| PATCH | `/platform/teacher-qualifications/{id}` | 暂停/撤销，If-Match；负责人阻断 |
| GET | `/platform/admin-assignments` | 管理员资格 |
| POST/PATCH | `/platform/admin-assignments...` | 授予/撤销，含最后管理员保护 |
| GET | `/platform/verifications` | 身份材料待审 |
| POST | `/platform/verifications/{id}/review` | 身份认证决定 |

教师资格撤销返回 blockers，例如仍为课程负责人。紧急 suspend 可立即禁止教师端登录，后续要求完成课程交接。

## 十二、管理端课程与运行治理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/platform/courses` | 全局课程监管只读列表 |
| GET | `/platform/courses/{id}` | 课程、任职、风险和资源摘要 |
| POST | `/platform/courses/{id}/freeze` | 合规冻结，必须原因/幂等/近期认证 |
| POST | `/platform/courses/{id}/unfreeze` | 恢复并审计 |
| GET/POST/PATCH | `/platform/runtime-adapters` | 运行时适配器 |
| GET/POST/PATCH | `/platform/images` | 镜像扫描/批准 |
| GET/POST/PATCH | `/platform/resource-profiles` | 资源规格 |
| GET/POST/PATCH | `/platform/quotas` | 平台/课程/用户配额 |
| GET | `/platform/instances` | 全局实例与孤儿检测 |
| POST | `/platform/instances/{id}/destroy` | 异常销毁，202、幂等、原因、近期认证 |
| GET/POST | `/platform/compensations` | 查看/重试可重试补偿 |
| GET | `/platform/outbox-events` | 事件/投递状态 |
| GET | `/platform/audit-logs` | cursor 审计检索 |
| GET/PUT | `/platform/security-policies` | 安全/网络/Agent 策略 |
| GET/PUT | `/platform/resource-scaling-policies` | 预热、扩缩容、空闲回收和预算护栏 |

冻结课程不等于直接删除任务或实例。冻结 service 根据风险策略撤销新写入、会话或触发回收，并保留课程和成果事实。

## 十三、教学分析与 Agent 治理

### 13.1 教师端分析

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/teaching/courses/{cid}/analytics/overview` | 课程参与、进度、实验和审核聚合趋势 |
| GET | `/teaching/courses/{cid}/analytics/risk-signals` | 可解释风险信号，按授权裁剪学生范围 |
| POST | `/teaching/courses/{cid}/analytics/risk-signals/{signal_id}/resolve` | 教师确认/忽略/关闭信号，幂等+If-Match |
| GET | `/teaching/courses/{cid}/analytics/quality` | 内容、实验、Agent 引用和反馈质量投影 |
| GET | `/teaching/courses/{cid}/analytics/resource-costs` | 本课程资源用量、预算和成本趋势 |

分析接口读取从 MySQL 业务事实生成、带 `projection_version/source_cursor` 的可重建投影。MongoDB 运行日志不作为教学分析事实源。风险信号和推荐不得自动退课、扣分、选课或改变任务/审核状态。

### 13.2 课程 Agent 配置

| 方法 | 路径 | 权限/说明 |
|---|---|---|
| GET/POST | `/teaching/courses/{cid}/agent-profiles` | `MANAGE_AGENT`；版本化配置列表/创建草稿 |
| GET/PATCH | `/teaching/courses/{cid}/agent-profiles/{profile_id}` | 编辑 DRAFT，选择模式、已批准路由、预算和工具集；If-Match |
| POST | `/teaching/courses/{cid}/agent-profiles/{profile_id}/evaluate` | 固定 profile/prompt/knowledge/tool-policy 版本启动评测，202、幂等 |
| POST | `/teaching/courses/{cid}/agent-profiles/{profile_id}/activate` | 仅评测达标后激活，幂等+If-Match |
| POST | `/teaching/courses/{cid}/agent-profiles/{profile_id}/retire` | 停止新会话，历史会话保持版本引用，幂等+If-Match |
| GET/POST | `/teaching/courses/{cid}/agent-knowledge-bases` | 知识库列表/创建 |
| GET/POST | `/teaching/courses/{cid}/agent-knowledge-bases/{kb_id}/sources` | 来源列表/登记课程资料、FAQ 或受控静态资料 |
| POST | `/teaching/courses/{cid}/agent-sources/{source_id}/versions` | 创建新来源版本并触发解析/索引，202、幂等 |
| GET | `/teaching/courses/{cid}/agent-ingestion-runs/{run_id}` | 解析、切分、索引和 ACL 校验结果 |
| GET/POST | `/teaching/courses/{cid}/agent-prompt-templates` | 课程指令模板列表/创建；不能覆盖平台安全提示词 |
| GET/POST | `/teaching/courses/{cid}/agent-prompt-templates/{template_id}/versions` | 不可变提示词版本列表/创建草稿版本 |
| GET/POST | `/teaching/courses/{cid}/agent-eval-suites` | 课程补充评测套件；不能删除平台强制用例 |
| GET/POST | `/teaching/courses/{cid}/agent-eval-suites/{suite_id}/cases` | 自定义题例、期望行为和期望引用 |
| GET | `/teaching/courses/{cid}/agent-eval-runs/{run_id}` | 分维度结果、失败样例、延迟和成本 |
| GET | `/teaching/courses/{cid}/agent-feedback` | 课程内脱敏反馈、教师标记和处理状态 |
| POST | `/teaching/courses/{cid}/agent-feedback/{feedback_id}/triage` | 标记问题类型/关闭，不直接进入训练集，幂等+If-Match |
| GET | `/teaching/courses/{cid}/agent-analytics` | 模式使用、引用覆盖、降级、反馈、延迟和成本聚合 |

知识源原文在 MinIO，MySQL 保存 source/version/digest/ACL/解析事实；向量或关键词索引均为可重建派生数据。检索前后都必须按 course、source version、audience 和 task scope 校验，教师不能查看学生的完整私密对话或借配置提升工具权限。

### 13.3 平台 Agent 与分析

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST/PATCH | `/platform/agent/model-routes` | 模型路由、fallback、预算和可用区域；写入 If-Match |
| GET/POST/PATCH | `/platform/agent/tool-policies` | 工具 schema、风险、参数脱敏、超时和输出限制 |
| GET/POST | `/platform/agent/eval-suites` | 平台强制安全/质量评测套件 |
| POST | `/platform/agent/eval-runs` | 对固定版本组合启动评测，202、幂等 |
| GET | `/platform/agent/eval-runs/{run_id}` | 越权、注入、引用、拒答、工具、延迟和成本结果 |
| GET | `/platform/agent/usage-costs` | 模型/token/检索/工具聚合成本，不返回敏感上下文 |
| GET | `/platform/analytics/quality` | 平台课程质量与投影新鲜度 |
| GET | `/platform/analytics/resource-costs` | Swarm、存储、模型和课程聚合成本 |
| GET | `/platform/analytics/projection-jobs` | 分析投影 cursor、延迟、失败和重建状态 |

## 十四、身份与开放集成

### 14.1 OIDC 管理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/platform/integrations/oidc-providers` | Provider 列表/创建；secret 仅写入不回显 |
| GET/PATCH | `/platform/integrations/oidc-providers/{id}` | issuer、client、claim mapping、portal 准入和状态；If-Match |
| POST | `/platform/integrations/oidc-providers/{id}/rotate-secret` | 近期认证、原因、幂等和双密钥过渡 |
| GET | `/platform/integrations/oidc-identities` | 按 provider/account/status 检索绑定 |
| POST | `/platform/integrations/oidc-identities/{id}/unlink` | 管理恢复操作，近期认证、原因和幂等 |

OIDC 身份以 `(issuer, subject)` 唯一绑定；不能根据 email 静默合并账号。回调不接受任意 redirect URI，解绑和恢复均写安全审计。

### 14.2 API Client 与 Webhook

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/platform/integrations/api-clients` | Client 列表/创建，初始 secret 只显示一次 |
| GET/PATCH | `/platform/integrations/api-clients/{id}` | 状态、允许 scopes、课程范围和限流；If-Match |
| POST | `/platform/integrations/api-clients/{id}/rotate-secret` | 近期认证、原因、幂等和双密钥过渡 |
| GET/POST | `/platform/integrations/webhook-endpoints` | Endpoint 列表/创建，校验 HTTPS 和事件 scope |
| GET/PATCH | `/platform/integrations/webhook-endpoints/{id}` | URL、事件、课程范围、状态；If-Match |
| POST | `/platform/integrations/webhook-endpoints/{id}/rotate-secret` | 签名密钥轮换，明文只显示一次 |
| GET | `/platform/integrations/webhook-deliveries` | delivery、attempt、状态、响应摘要和 dead-letter |
| GET | `/platform/integrations/webhook-deliveries/{id}/attempts` | 只追加尝试时间线、请求 digest 和脱敏响应摘要 |
| POST | `/platform/integrations/webhook-deliveries/{id}/retry` | 仅失败/死信投递，幂等、原因和审计 |
| POST | `/integrations/oauth/token` | client credential 换取短期 access token；不用 Session/CSRF，独立限流 |
| GET | `/integrations/open/courses` | 示例开放 API；按 token scope 和课程 grant 查询 |
| GET | `/integrations/open/courses/{id}/experiments` | 示例课程实验只读接口，复用课程 selector |
| GET | `/integrations/open/courses/{id}/progress` | 示例聚合进度接口，禁止泄露非授权学生明细 |

Webhook 使用 `delivery_id + timestamp + body digest` 的 HMAC 签名，接收方可做重放保护；delivery 保存可变调度状态，每次网络请求追加不可变 attempt，服务端指数退避并保留死信。开放 API 只暴露 OpenAPI 中显式标记的稳定路径，不把浏览器 Session、教师页面接口或管理端能力直接转为 client scope。

首期明确不提供 Moodle、Canvas、LTI、成绩回传或其他 LMS 专用连接器。通用 OIDC、scope 化开放 API 和签名 Webhook 是唯一开放集成面。

## 十五、通知

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/notifications` | 当前 portal/账号可见通知 |
| POST | `/notifications/{id}/read` | 标记已读 |
| GET/PATCH | `/notification-preferences` | 当前账号偏好 |

通知链接包含目标站点的普通 HTTPS URL 和 opaque ID，不携带 Session/token。打开另一门户时由目标站独立登录和判权。

不提供 PWA Push、离线通知或独立移动端只读通知 API；通知中心是三端网页内能力。

## 十六、SSE

```http
GET /api/v2/events/stream
Accept: text/event-stream
Last-Event-ID: 1726639200000-1
```

服务端根据 portal 和当前对象 scope 自动订阅，不接受客户端任意声明 `course:*` 频道。事件格式：

```text
id: 1726639200000-2
event: task.status_changed
data: {"subject_id":"EXP-...","course_id":"01...","from":"PROVISIONING","to":"READY","trace_id":"..."}
```

响应头：`Cache-Control: no-cache, no-transform`、`X-Accel-Buffering: no`。心跳不改变业务状态。超出续传窗口发送 `resync.required`，前端全量刷新相关 query。

## 十七、文件和工作区网关

### 上传

`multipart/form-data`，先校验大小、扩展名、MIME/magic、ClamAV，再登记资产。异步扫描返回 202 时，业务对象不能在扫描通过前引用该资产。

### 下载

```text
POST /api/v2/files/{asset_id}/download-grants
GET  /files/{one_time_token}
```

授权 service 校验 portal、本人/课程 scope、用途和保留状态。token 短期、限次数、数据库只存 hash。

### 工作区

```text
/workspace/{session_public_id}/...
```

只允许 user-web Session/工作区票据，网关每次检查票据、task、student、instance 和撤销状态。teacher/admin 站点不得代理到学生工作区。

## 十八、幂等与 If-Match 清单

### 必须 Idempotency-Key

- 所有创建资源、触发异步作业、状态跃迁、审批、撤销、恢复、重试、导出、密钥轮换和高风险处置 POST 都必须携带。
- 仅以下 POST 例外：`/auth/login`、`/auth/logout`、`/auth/logout-all`、`/integrations/oauth/token`，以及无副作用但为避免 secret 进入 URL 而使用 POST 的 `/course-invitations/resolve`。
- 服务端先完成认证和对象 scope，再按 actor/auth-context + endpoint + key + request digest 查询幂等记录；精确重放直接返回原响应，新请求才检查当前状态和 If-Match。

### 必须 If-Match

- 所有 Versioned 资源的 PATCH/PUT 必须携带。
- 对现有 Versioned 聚合执行 publish/withdraw/close/archive/transfer/approve/reject/start/enter/submit/retry/restore/activate/retire/rotate/revoke 等状态跃迁 POST 必须携带。
- 创建全新聚合的 POST、只追加子事实且不依赖可变父状态的 POST，以及明确无副作用的查询不要求；若追加动作受父状态约束，则携带父资源 ETag。

不可变 AppendOnly 资源没有 PATCH/DELETE。

## 十九、OpenAPI 分组与接口验收

OpenAPI tag 固定包含：`auth`、`me`、`courses`、`tasks`、`workspaces`、`reports`、`agents`、`notifications`、`teaching-courses`、`teaching-content`、`teaching-enrollments`、`teaching-experiments`、`teaching-reviews`、`teaching-analytics`、`teaching-agents`、`platform-accounts`、`platform-governance`、`platform-agents`、`platform-analytics`、`platform-integrations`、`external-api` 和 `events`。

- OpenAPI 路径按 tag 分组，三端客户端只导入所属分组。
- 每个写接口覆盖 portal、对象 scope、状态、幂等、并发和审计。
- 不可见对象 404，不通过响应差异泄露其他课程/学生。
- Session portal mismatch、资格撤销、退课后的旧票据均有集成测试。
- 异步接口不会在外部 I/O 完成前返回伪成功。
- API 变更通过 OpenAPI schema diff 和三端联合构建门禁；不提供旧系统 v1 兼容层，但本项目 `/api/v2` 在三端独立滚动发布期间必须保持向后兼容，破坏性变更使用新 major path 或双 revision。
- Agent 引用访问、跨课程检索拒绝、无来源降级、评测门禁和工具二次授权有契约测试。
- 批量导入逐行幂等、课程复制、延期并发、检查点恢复、Rubric、相似度辅助和分析投影新鲜度有集成测试。
- OIDC issuer+subject 唯一、API scope/课程范围、Webhook 签名/重放/重试/死信有安全测试。
- 不生成 LMS 专用路径，也不生成 PWA、离线通知、独立移动端只读、国际化或专项无障碍接口。
