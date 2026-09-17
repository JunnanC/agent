# 多Agent智能虚拟化实验平台产品需求文档（PRD）

**版本：** v1.0  
**日期：** 2026-09-15  
**状态：** 开发前置基线，待立项评审冻结  
**适用范围：** 第一阶段单团队 PC Web 平台

## 1. 文档目的与决策优先级

本 PRD 是项目实施、接口联调、测试验收和需求变更的统一入口。它约束第一阶段必须交付的业务闭环、技术选择、数据边界和质量门禁，不以页面原型或临时演示数据代替服务端业务事实。

当文档出现冲突时，按以下顺序处理：

1. 本 PRD：第一阶段实施范围、架构和验收的统一基线。
2. `documents/Guideline/01` 至 `10`：各领域详细说明、追踪矩阵和页面验收补充。
3. `documents/Preparation/附件5：数据库设计文档.docx` v1.0：字段、索引、外键、迁移和数据治理权威来源。
4. UI 原型：仅用于信息架构、交互状态与视觉验收，不能定义授权、状态终态或数据事实。

任何影响角色、业务状态、数据库实体、接口、运行时、归档策略或 P0 指标的调整，必须先更新本 PRD、需求追踪矩阵和对应设计文档，再进入代码开发。

## 2. 产品定义

多Agent智能虚拟化实验平台是一套面向教学、训练和实验实践的浏览器端云实验平台。教师使用已发布且不可变的模板版本创建实验任务并指定用户；平台自动准备容器或虚拟机环境；用户在受控工作区完成实验并保存过程；报告或系统成果经审核、归档校验后，平台撤销访问、销毁实例并释放配额。

```text
用户申请加入/教师直接添加 -> 成员成为 ACTIVE
-> 教师创建模板、预检并发布版本 -> 发布任务并指定 ACTIVE 用户
-> 用户启动任务 -> 自动装载容器或虚拟机 -> 签发短期工作区会话
-> 实验保存 -> 报告或系统成果提交 -> 审核通过或退回
-> 归档与摘要校验 -> 撤销会话 -> 销毁实例 -> 释放配额 -> 完成
```

平台不是模板市场、通用云主机控制台、在线刷题平台或无约束聊天工具。普通用户不安装本地运行时，也不能自主选择镜像、虚拟机模板、依赖、网络策略或资源规格。

## 3. 目标、范围与优先级

### 3.1 第一阶段目标

1. 跑通教师发布到归档销毁的完整闭环，并支持容器和虚拟机两类运行时。
2. 以固定 RBAC、成员资格、任务分配和数据范围保证服务端授权。
3. 支持幂等环境装载、阶段进度、SSE 续传、失败诊断、有限重试、取消和补偿。
4. 提供 WebIDE、Notebook、Web 终端、Web 预览、浏览器远程桌面等由模板决定的工作区能力。
5. 在实例销毁前将报告、附件、快照、日志和成果持久化并完成归档校验。
6. 在任务列表、装载、工作区和报告阶段提供受控 Agent 辅助，并落实上下文隔离、审批和审计。

### 3.2 P0 范围

| 领域 | 必须交付的能力 |
|---|---|
| 身份与成员 | 账号密码登录、固定四角色、加入申请、审核、直接添加、退出、移除、最后管理员保护 |
| 模板与任务 | 模板草稿、预检、不可变版本、任务发布、ACTIVE 成员分配、撤回 |
| 实验运行 | Docker/OCI 和 libvirt/KVM、统一适配器、配额、装载、SSE、重试、取消、补偿 |
| 工作区 | 材料、起始资源、平台网关、短期会话、过程保存和撤销 |
| 成果闭环 | 报告草稿与版本、附件、审核、退回、成果清单、归档、导出、销毁 |
| Agent | 当前授权上下文、手册解释、错误诊断、风险审批、调用审计 |
| 运维治理 | 配额、审计、Outbox、监控、异常实例人工处置、备份恢复 |

### 3.3 延后范围

- P1：Agent 自动修复、复杂多 Agent 工作流、丰富自动评测、教学分析和批量导出。
- P2：协作实验、模板市场、能力画像、多租户、私有化增强、跨地域容灾和移动原生应用。

### 3.4 明确禁止

- USER 自由创建环境、自配镜像/依赖/资源、创建个人模板或访问未分配任务。
- 浏览器直接访问容器端口、虚拟机管理 API、对象存储管理凭据或运行时管理接口。
- 以浏览器计时器、内存状态、Mock 数据或占位下载认定审核、归档、销毁等业务终态。
- AI 未经审批执行写文件、删文件、安装依赖、联网或高风险命令。
- 以 Redis、前端缓存或实例临时磁盘作为报告、审核、配额、归档或任务状态的唯一事实来源。

## 4. 角色与权限

| 角色 | 权限边界 |
|---|---|
| `USER` | 申请或退出团队；查看本人已分配任务；启动、使用工作区、保存、提交报告或成果；查看审核、归档和通知；使用受控 Agent |
| `ORG_SUB_ADMIN` | 在获授权任务范围发布任务、查看过程、审核和导出；默认不能管理成员或全局配置 |
| `ORG_ADMIN` | 审核、直接添加和移除成员；管理模板版本；发布或撤回任务；查看授权成果与审核 |
| `SYSTEM_ADMIN` | 管理固定角色、管理员交接、运行时、白名单、配额、安全、补偿和审计；不能替代教师写业务审核结论 |

账号、固定角色和团队成员资格是独立事实。平台第一阶段只有一个团队，成员状态为 `PENDING`、`ACTIVE`、`REJECTED`、`EXITED`、`REMOVED`；仅 `ACTIVE` 成员可被新分配或启动实验。前端隐藏入口只改善体验，后端每次读取和写入都必须校验角色、数据范围、资源归属、成员资格、任务状态和时间窗口。

成员退出或移除必须阻断未完成任务、活动实例、待审核、归档和销毁流程；成功后撤销会话，保留成员、任务、报告、归档和审计历史。最后一名有效 `ORG_ADMIN` 只能由 `SYSTEM_ADMIN` 完成交接后再处理。

## 5. 核心业务规则与状态机

### 5.1 模板、任务和实例

- 只有预检通过的模板版本可以发布；任务发布后固定引用模板版本，禁止原地修改。
- 任务仅向 `ACTIVE` 成员创建分配，启动时必须再次读取当前成员资格。
- 实例只能由 `experiment_task_assignments` 触发，不能由用户 ID 与模板 ID 直接创建。
- `start` 必须幂等；重复点击、刷新或重放请求只能复用同一装载作业和实例。
- 用户工作区只展示冻结模板允许的接入能力，访问凭据短期有效且可被立即撤销。

### 5.2 用户任务状态

```text
ASSIGNED -> PROVISIONING -> READY -> IN_PROGRESS

报告必交：IN_PROGRESS -> REPORT_DRAFT -> UNDER_REVIEW -> APPROVED
                                      ^          |
                                      |          -> REJECTED

报告非必交：IN_PROGRESS -> UNDER_REVIEW -> APPROVED
                         ^       |
                         |       -> REJECTED -> IN_PROGRESS

APPROVED -> ARCHIVING -> DESTROYING -> COMPLETED
任意异步阶段可进入 FAILED；任务撤回进入 CANCELLED。
```

失败记录必须至少包含失败阶段、前序状态、错误码、脱敏原因、是否可重试、重试次数和 `trace_id`。自动重试达到上限后进入人工处置，禁止无限重试。

### 5.3 报告、审核和归档

- `report_required=true` 时，报告正文、附件、快照和关键日志必须冻结为提交版本。
- `report_required=false` 时，用户结束实验由编排服务生成包含快照、运行结果、日志和产物清单的系统成果版本，仍须审核。
- 审核支持人工、自动和复合三种模式；退回必须产生新的可编辑版本，历史版本只读。
- 归档必须包含通过版本、附件、快照、日志、评测结果和必要产物；文件与整体清单均校验 SHA-256。
- 只有归档状态为 `COMPLETED` 且摘要校验通过，才能撤销访问并销毁运行时资源。

## 6. 页面与交互要求

| 身份 | 页面范围 | 核心要求 |
|---|---|---|
| USER | 我的团队、任务列表与详情、装载、云端实验室、报告/成果、通知 | 只显示本人有效分配；流程状态来自接口或事件；完整覆盖加载、空、无权限、提交中、失败、断网和恢复状态 |
| ORG_ADMIN | 成员、模板、任务发布、过程追踪、待审、归档 | 发布时仅可选择 ACTIVE 成员；模板版本和任务策略可追溯；过程按用户查看 |
| SYSTEM_ADMIN | 用户与固定角色、运行时、资源、实例、补偿、Agent/模型、安全与审计 | 列表均服务端分页和过滤；高风险操作二次确认、幂等、审计和失败处置 |

装载页面必须显示阶段、步骤、耗时、进度、错误摘要、`retryable` 和 `trace_id`。提交确认必须展示被冻结的报告版本、快照、运行结果、关键日志和产物。Agent 浮层可鼠标或键盘打开，具有可见焦点和 `aria-label`，不得遮挡保存、提交或移动端底部操作区。

主验收视口为 1440 px，920 px 与 390 px 不得出现主体横向溢出；支持 Chrome 和 Edge 最近两个主版本，状态不得只通过颜色表达。

**UI 与可访问性约束（与 `02_角色权限与业务流程.md` §8 逐条等价，任一侧改动必须同步另一侧）：**

- 实验列表、装载、工作区和报告页始终提供 Agent 入口；任务上下文切换后必须同步切换 Agent 上下文。
- 装载、归档和销毁使用同一阶段时间线表达等待、处理中、成功、失败和可重试状态。
- 工作区固定提供实验手册、起始资源、结果区和流程入口，关键操作不得被悬浮控件遮挡。
- 悬浮 Agent 支持鼠标、键盘焦点、`aria-label` 和文本提示；移动端自动避让底部操作区。
- 停止、提前结束、撤回和强制销毁必须二次确认，明确保存、快照、访问中断和不可逆影响。
- “我的团队”页必须展示成员状态、申请处理说明和退出阻断事项；非ACTIVE成员任务页显示资格原因与团队入口。
- “团队成员”页仅对ORG_ADMIN可见，支持状态筛选、申请审核、按账号直接添加和移除确认；移除确认必须显示阻断事项及最后管理员保护。

## 7. 技术路线与系统架构

### 7.1 冻结技术栈

| 层级 | 第一阶段方案 |
|---|---|
| 前端 | React 18、TypeScript 5、Vite、由 OpenAPI 生成客户端类型 |
| API | Python 3.12、Django 5、Django REST Framework、drf-spectacular/OpenAPI 3.0 |
| 数据与异步 | MySQL 8.0、Redis 7、Celery 5 |
| 文件存储 | MinIO（S3 兼容） |
| 事件与观测 | SSE、JSON 结构化日志、Prometheus、OpenTelemetry |
| 容器运行时 | Docker Engine/OCI |
| 虚拟机运行时 | libvirt/KVM、Cloud-init |
| 测试与安全 | pytest、Django test、Playwright、k6、OWASP ZAP |

Kubernetes、KubeVirt、PostgreSQL、FastAPI、WebSocket、云厂商运行时不属于第一阶段主路径。

### 7.2 架构原则

1. 第一阶段采用模块化单体加独立 Worker；模块拥有清晰的数据、事务和应用服务边界。
2. 浏览器只经平台网关访问工作区和受控下载地址。
3. 运行时统一通过 `RuntimeAdapter`，业务服务不得直接耦合 Docker、libvirt 或云厂商 SDK。
4. 长任务由 Celery 执行，通过 SSE 发布事件；本地事务只写业务事实、Outbox 和审计，不等待外部运行时完成。
5. MySQL 是唯一业务事实源；Redis 仅用于缓存、锁、限流、队列和短期状态。

`RuntimeAdapter` 必须实现：

```text
validate_spec(spec)
create(spec, idempotency_key)
get_status(runtime_instance_id)
get_progress(runtime_instance_id)
issue_access(runtime_instance_id, user_id, access_mode)
snapshot(runtime_instance_id, policy)
stop(runtime_instance_id)
destroy(runtime_instance_id, idempotency_key)
collect_metrics(runtime_instance_id)
```

运行参数必须由服务端根据冻结模板、任务策略、配额、白名单和安全策略生成，不接受 USER 提交的镜像、路径、依赖、网络或资源规格。

### 7.3 一致性与补偿

```text
API 事务：业务状态 + 审计 + Outbox
      -> Worker：发布事件或调用 RuntimeAdapter
      -> SSE：推送可续传阶段事件
      -> 失败：compensation_jobs 重试或转人工处置
```

所有跨服务副作用必须有超时、有限重试、幂等键、结构化日志、`request_id` 和 `trace_id`。Outbox 消费者以 `event_id` 去重；SSE 客户端以 `Last-Event-ID` 续传和去重。运行时已成功而数据库失败、归档部分完成、会话撤销或配额释放不确定时，必须通过补偿任务查询外部事实后收敛。

## 8. 数据库设计与数据治理

字段、外键、索引和迁移以 v1.0 数据库设计文档为权威；本节定义开发时不得违反的聚合与数据规则。

| 领域 | 核心表 |
|---|---|
| 身份与成员 | `users`、`roles`、`team_settings`、`team_memberships`、`user_verifications`、`user_quotas` |
| 模板与任务 | `experiment_templates`、`experiment_template_versions`、`template_assets`、`experiment_tasks`、`experiment_task_assignments`、`task_materials` |
| 实例与会话 | `experiment_instances`、`instance_provisioning_jobs`、`instance_provisioning_steps`、`instance_events`、`workspace_access_sessions` |
| 报告与成果 | `experiment_reports`、`experiment_report_versions`、`experiment_report_files`、`experiment_report_reviews`、`experiment_archives`、`experiment_archive_files` |
| 可靠性与审计 | `files`、`notifications`、`outbox_events`、`compensation_jobs`、`audit_logs` |
| Agent 与评测 | `agent_runs`、`assistant_conversations`、`assistant_messages`、`tool_call_logs`、`model_providers`、`model_call_logs`、`evaluation_rules`、`evaluation_jobs`、`evaluation_results` |

核心关系如下：

```text
team_memberships -> experiment_task_assignments -> experiment_instances
experiment_templates -> experiment_template_versions -> experiment_tasks
experiment_task_assignments -> experiment_reports -> experiment_report_versions
experiment_task_assignments -> experiment_archives -> experiment_archive_files
```

`experiment_task_assignments` 是用户流程聚合根。分配记录保存任务发布时的 `team_membership_id` 快照，但启动仍必须检查当前成员为 `ACTIVE`。已提交的报告版本、审核结论、归档清单、事件和审计日志只追加写入，禁止原地覆盖。

文件正文、附件、日志和快照存入 MinIO，数据库只保存元数据、归属、状态、摘要和引用关系。工作区会话仅保存令牌 JTI 摘要，不保存明文 Token、远程桌面密码、云密钥或完整敏感 Agent 上下文。

发布任务、启动实验、成员变更、报告提交、审核、归档与回收必须将业务事实、审计和 Outbox 在同一数据库事务中提交。所有数据库变更必须使用 Django migration，并提供空库、升级、回滚或恢复说明。

## 9. 接口与集成约束

接口统一使用 `/api/v1` 和 OpenAPI 3.0。响应使用 UTF-8 JSON，列表响应统一包含 `data.items`、`page`、`page_size`、`total` 和 `request_id`；文件使用受控、短期、绑定资源的预签名 URL。

### 9.1 关键接口组

| 接口组 | 示例路径 | 规则 |
|---|---|---|
| 用户成员与任务 | `/me/team-membership`、`/me/experiment-tasks` | 仅返回本人且当前可访问资源 |
| 装载与工作区 | `/me/experiment-tasks/{assignmentId}/start`、`/events`、`/workspace-sessions` | `start` 返回 202 与 `operation_id`；SSE 支持 `Last-Event-ID` |
| 报告与成果 | `/report/draft`、`/report/submit`、`/artifact/submit`、`/archive` | 草稿使用 ETag/revision；提交由服务端冻结证据 |
| Agent | `/me/agent/conversations`、`/messages`、`/tool-approvals` | 会话绑定授权任务；高风险工具先返回审批状态 |
| 教学管理 | `/teaching/team-members`、`/experiment-templates`、`/experiment-tasks`、`/report-reviews` | 角色、授权任务范围和 ACTIVE 资格均由服务端校验 |
| 系统管理 | `/admin/users`、`/runtime-adapters`、`/instances`、`/compensation-jobs`、`/audit-logs` | 危险操作需确认、幂等与审计 |

所有改变业务事实或触发外部动作的接口必须携带 `Idempotency-Key`，服务端至少保留 24 小时；同一键重放返回原状态和响应，不同请求摘要复用同一键返回 `IDEMPOTENCY_CONFLICT`。写操作使用 `If-Match`/ETag 或 `revision` 防止覆盖较新版本。异步动作返回 `operation_id` 和 `trace_id`。

错误响应不得暴露 SQL、堆栈、内网地址、凭据或他人资源是否存在。统一错误包括：`VALIDATION_ERROR`、`UNAUTHENTICATED`、`FORBIDDEN`、`MEMBERSHIP_REQUIRED`、`STATE_CONFLICT`、`IDEMPOTENCY_CONFLICT`、`QUOTA_EXCEEDED`、`PRECHECK_FAILED`、`RUNTIME_UNAVAILABLE`。

## 10. 开发规范与协作约束

1. 采用主干开发或短生命周期功能分支；一个模块任务对应一个可审查变更集，不混入无关重构。
2. OpenAPI、事件 Schema、数据库迁移、错误码、权限矩阵和追踪矩阵是联调前置物；前端不得自行拼接未约定接口或假定未定义字段。
3. Python 使用类型标注、领域化命名、简洁文档字符串和结构化日志；遵循仓库 `pyproject.toml` 中 Ruff 的格式与静态检查约束。
4. 前端页面按领域拆分，接口访问集中封装；加载、空、权限、失败、网络中断和异步状态必须显式实现，禁止以 `any` 或本地假数据绕过契约。
5. 不提交密码、令牌、真实个人数据、生产导出、未脱敏日志或运行时管理凭据。配置经受控环境变量或密钥服务注入。
6. 每个写接口必须有权限、状态迁移、幂等、并发冲突和审计测试；每个外部调用必须设置超时、重试上限和可观测性字段。
7. 代码评审必须检查数据范围、敏感信息、状态机、迁移、补偿、测试和文档是否同步更新。

## 11. 开发步骤与里程碑

| 阶段 | 时间 | 核心产出 | 退出条件 |
|---|---:|---|---|
| G0 范围冻结 | 第 1 周 | PRD、P0 边界、风险清单、142 功能点映射 | 无阻塞性业务或技术二选一 |
| G1 契约与骨架 | 第 1 周 | Django/React 工程骨架、OpenAPI、迁移基线、Fake Adapter、Mock | 前后端可基于稳定契约开发 |
| G2 容器主链路 | 第 2-3 周 | 成员资格、模板任务、容器装载、SSE、用户端页面 | 20 个并发启动无重复实例 |
| G2V 虚拟机链路 | 第 4 周 | KVM Adapter、Cloud-init、访问、快照与销毁 | 虚拟机 10 次完整冒烟通过 |
| G3 报告与 Agent | 第 4-6 周 | 报告版本、审核、归档前置、受控 Agent | 退回重提、并发保存和审批可测 |
| G4 生命周期收敛 | 第 6-7 周 | 归档 manifest、会话撤销、双运行时销毁、配额与补偿 | 重放和部分成功场景收敛 |
| G5 集成质量 | 第 8-9 周 | 全量 E2E、性能、安全、恢复演练 | 所有 P0 验收通过 |
| G6-G8 UAT 与交付 | 第 10-12 周 | UAT、上线准备、7 天试运行、交付材料 | 无 P0 事故，P1 有计划和负责人 |

推荐模块责任流：后端 1 负责工程基础、身份授权、工作区网关和 Agent；后端 2 负责模板任务、报告审核归档；后端 3 负责编排、容器和虚拟机；前端页面由三名后端按域切片先完成 USER 主链路再实现教学与管理端；测试运维从第一天提供 CI、Mock、环境、监控和质量门禁。

## 12. 测试、验收与上线门禁

### 12.1 P0 验收重点

- 四角色路由正确，USER 无法通过页面或直接 API 创建模板、发布任务、创建未分配实例或访问他人数据。
- 加入、审核、直接添加、退出、移除和最后管理员保护完整可追溯；非 ACTIVE 成员无法被分配、启动或获得工作区会话。
- 容器与虚拟机均完成创建、访问、快照、销毁和失败收敛；重复启动不会创建第二实例。
- SSE 支持续传去重；装载、报告、审核、归档、销毁等页面状态均有接口或事件事实。
- 报告和非必交成果均产生不可篡改证据；归档未完成或摘要不匹配时不能销毁。
- Agent 的高风险操作 100% 进入审批和审计；所有关键动作可按 `assignment_id`、`instance_id`、`request_id` 或 `trace_id` 检索。

### 12.2 非功能基线

| 指标 | 最低验收标准 |
|---|---|
| 容量 | 100 名并发在线用户、50 个并发实例、20 个并发启动请求 |
| API 性能 | 读接口 P95 <= 500 ms，普通写接口 P95 <= 800 ms，不含文件传输和长任务 |
| 环境启动 | 已缓存镜像的容器 P95 <= 120 秒；预热虚拟机模板 P95 <= 300 秒 |
| 事件与保存 | 事件 P95 <= 2 秒；断线 5 秒内续传；自动保存间隔 <= 10 秒，RPO <= 30 秒 |
| 回收与可用性 | 销毁指令后资源释放 P95 <= 5 分钟；UAT 连续 7 天核心 API 可用性 >= 99.5% |
| 恢复与存储 | MySQL RPO <= 24 小时、RTO <= 4 小时；归档抽样恢复 100%；对象存储至少 1 TB |

### 12.3 上线阻断条件

- 任一越权路径、非 ACTIVE 成员启动路径、未分配实例创建路径或失效会话继续访问路径存在。
- 容器或虚拟机任一运行时不能完成 P0 生命周期，或重复请求导致重复实例、重复扣/释配额。
- 归档未校验即销毁、提交证据可覆盖或伪造、异步失败无补偿或人工入口。
- Outbox、SSE 或通知无法去重、续传或追溯；关键审计缺失或包含明文凭据。
- 不满足性能、恢复、安全、可访问性和响应式基线。

## 13. 交付物与变更管理

每个模块交付必须同时包含：实现代码、OpenAPI 或事件 Schema、数据库迁移、权限和错误码说明、单元/接口/契约测试、关键 E2E 证据、监控字段、运行与回滚说明，以及追踪矩阵更新。

需求变更必须记录变更原因、影响范围、优先级、接口和迁移影响、测试项、负责人和生效版本。未经记录的变更不得进入联调或上线候选版本。

---

## 附：权威关联文档

- `documents/Guideline/01_产品范围与需求基线.md`
- `documents/Guideline/02_角色权限与业务流程.md`
- `documents/Guideline/03_技术路线与系统架构.md`
- `documents/Guideline/04_数据库设计与数据治理.md`
- `documents/Guideline/05_接口设计与集成规范.md`
- `documents/Guideline/06_开发规范与项目约束.md`
- `documents/Guideline/08_测试验收与风险控制.md`
- `documents/Guideline/10_需求追踪矩阵.md`
- `documents/Preparation/附件5：数据库设计文档.docx`

> 注：原附录中的 `需求变更说明_教师发布与云端实验全流程.md` 已取消（2026-09-17，D1）；`第三批文档/` 为本仓库 `documents/Guideline/` 的旧逻辑路径，已统一；`11_页面原型驱动补充需求.md` 已停用（2026-09-17），不再作为关联文档。
