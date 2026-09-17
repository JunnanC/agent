# Agent 层数据库表设计（v1.0 同步版）

> ✅ **本文件为 M6 Agent 域数据模型的活动设计资产**（2026-09-17 按 `附件5：数据库设计文档.docx` v1.0 同步重建，替代原 2026-09-10 降级的历史资产）。
> **权威依据**：字段、索引、外键与事务约束以数据库设计文档 **v1.0**（`documents/Preparation/附件5：数据库设计文档.docx`）为唯一权威，本文件只按域切片摘取 Agent 相关表并补充模块口径，**不得与附件5 冲突**；冲突时以附件5 为准。
> **数据库**：MySQL 8.0，库名 `agent_virtual_lab`（与平台业务表同库，非独立 `agent` 库）。
> **配套文件**：`DESIGN/SQL/AGENT_DB.sql`（v1.0 建表脚本）、`DESIGN/ER/AGENT_DB.mmd`（v1.0 ER 图）。
> **使用口径**：M6 Agent 与策略网关模块按本文件与附件5 v1.0 建表；原历史资产中的 `agent_tasks`、`agent_task_runs`、`agent_tool_definitions`、`agent_workflows`、`prompt_versions`、`model_configs`、`agent_roles` 等旧表名在 v1.0 中不存在，不得再使用。

> **变更记录**
> - v1.0（2026-09-17）：按数据库设计文档 v1.0 全量同步。Agent 域收敛为 13 张表（Agent 业务 4 + 评测与模型调用 5 + 可靠性 4），主键由旧 `char(36)` UUID 改为 `BIGINT UNSIGNED` 自增，跨域字段改为 `assignment_id`/`user_id` 等平台主键并建立物理外键；触发器、视图、存储过程按附件5 口径说明。本版起为活动资产，不再是历史资产。
> - v1.1（2026-09-10，历史冻结）：`organization_id` 语义改为 `team_id`；该版及其前身 v1.0（2026-09-08）均为已降级历史基线，仅作留档。

## 1. 设计结论

Agent 模块是「受控上下文助手 + 高风险审批 + 调用审计」：Agent 在列表、装载、工作区和报告阶段可达，上下文只含当前授权对象（任务/实例/手册/文件/日志），写删文件、安装依赖、联网和高风险命令进入策略审批与审计（见 `AGENTS.md`「Agent 受控辅助」与 `01_产品范围与需求基线.md` §3 Agent P0 条目）。

Agent 域共 13 张表，按附件5 域映射组织：

| 分类 | 表 | 用途 |
|---|---|---|
| Agent 业务 | `agent_runs` | Agent 运行表：一次对话补全运行（含 token、时延、错误与追踪） |
| Agent 业务 | `assistant_conversations` | Agent 会话表：绑定任务分配，保存授权对象白名单，每用户每分配至多一个活跃会话 |
| Agent 业务 | `assistant_messages` | Agent 消息表：会话消息（USER/ASSISTANT/SYSTEM/TOOL），只追加，自增主键即消息游标 |
| Agent 业务 | `tool_call_logs` | 工具调用与审批记录表：风险等级、审批状态、一次性审批凭据摘要与执行结果 |
| 评测与模型调用 | `evaluation_rules` | 评测规则表：随模板版本冻结 |
| 评测与模型调用 | `evaluation_jobs` | 评测任务表：一次评测运行，幂等键防重复触发 |
| 评测与模型调用 | `evaluation_results` | 评测结果表：一次运行对多条规则的结论（父子关系） |
| 评测与模型调用 | `model_providers` | 模型提供方表：网关端点与凭据引用，不下发前端 |
| 评测与模型调用 | `model_call_logs` | 模型调用日志表：Agent 与评测两侧调用统一记账（只追加） |
| 可靠性 | `outbox_events` | Outbox 事件表（只追加）：事件去重与投递 |
| 可靠性 | `compensation_jobs` | 补偿任务表：失败收敛与人工处置 |
| 可靠性 | `notifications` | 通知表：Outbox 消费生成 |
| 可靠性 | `audit_logs` | 审计日志表（只追加）：统一审计索引，含 Agent 工具审批动作 |

Agent 模块不复制平台用户、任务分配、模板版本、实例与文件主数据；通过 `assignment_id`、`user_id`、`template_version_id`、`instance_id`、`file_id` 等平台主键在库内建立物理外键关联（同一 `agent_virtual_lab` 库）。

## 2. 边界与不变量

### 2.1 跨域边界

- Agent 上下文只绑定当前授权对象：`assistant_conversations.context_json` 为授权对象白名单（任务/实例/手册/文件/日志），**不得含其他任务**；`assignment_id`、`user_id` 必填且由业务服务在写入前校验 ACTIVE 成员资格与归属。
- Agent 是平台内部参与者，不是用户角色；审批人是平台 `users`（`approved_by_id`），系统/编排写入 `audit_logs.actor_user_id = NULL`。
- 策略引擎与工具网关是外部权威组件：`tool_call_logs` 保存风险等级、审批状态、一次性审批凭据 JTI 摘要与结果摘要，用于追溯但不取代策略表。
- 模型凭据只存引用（`credential_ref`、`approval_token_jti_hash`），不存明文；`model_providers.base_url` 仅服务端可见，不下发前端。

### 2.2 复现和一致性不变量

- `assistant_messages`、`model_call_logs`、`audit_logs`、`outbox_events` 只追加，不更新、不物理删除。
- `assistant_conversations` 通过 `active_ctx_key` 辅助列实现「每用户每分配至多一个活跃会话」的部分唯一约束：活跃会话置常量、其余置 NULL，复合唯一 `(active_ctx_key, user_id)`。
- `tool_call_logs` 高风险动作必须先审批后执行：`approval_status` 为 `PENDING` 时 `status` 必须为 `PENDING_APPROVAL`；被拒绝或参数非法时状态只能为 `DENIED`/`BLOCKED`，不得进入 `RUNNING`。
- `evaluation_jobs` 以 `idempotency_key` 唯一防重复触发；同一幂等键下用 `attempt_no` 表达重试。
- `model_call_logs` 的 `job_id`/`run_id` 按 `call_type` 二选一：`EVALUATION` 时 `job_id` 非空、`AGENT_CHAT` 时 `run_id` 非空。
- `audit_logs` 只追加，修正通过新事件表达；`before_json`/`after_json` 为脱敏快照，`ip` 脱敏、`user_agent_hash` 存摘要。
- 完整请求/响应原文、完整工具入参与长输出放 MinIO：`model_call_logs.request_object_key/response_object_key`、`evaluation_results.evidence_file_id`；MySQL 只保留脱敏摘要、哈希、对象引用与元数据。

## 3. 库表字段表格

以下字段、类型、长度、空值、PK/FK、说明与枚举值**逐字对齐附件5 v1.0**；主键均为 `BIGINT UNSIGNED` 自增；时间统一为 UTC `datetime(6)`。

### 3.1 Agent 业务表

| 表 | 字段（类型） | 约束/说明 |
|---|---|---|
| `agent_runs` | `id BIGINT UNSIGNED`；`conversation_id BIGINT UNSIGNED`；`assignment_id BIGINT UNSIGNED`；`user_id BIGINT UNSIGNED`；`status VARCHAR(32)`；`model_name VARCHAR(128)`；`prompt_tokens INT UNSIGNED`；`completion_tokens INT UNSIGNED`；`tool_call_count INT UNSIGNED`；`latency_ms INT UNSIGNED`；`error_code VARCHAR(64)`；`error_message VARCHAR(512)`；`trace_id VARCHAR(64)`；`started_at DATETIME(6)`；`finished_at DATETIME(6)`；`created_at DATETIME(6)` | PK `id`；FK `conversation_id→assistant_conversations.id`、`assignment_id→experiment_task_assignments.id`、`user_id→users.id`；状态 `PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED`；`created_at` 只追加；索引 `idx_run_conv_time(conversation_id, created_at)`、`idx_run_assign(assignment_id)`、`idx_run_trace(trace_id)` |
| `assistant_conversations` | `id BIGINT UNSIGNED`；`assignment_id BIGINT UNSIGNED`；`user_id BIGINT UNSIGNED`；`title VARCHAR(255)`；`status VARCHAR(32)`；`context_json JSON`；`last_message_at DATETIME(6)`；`active_ctx_key BIGINT UNSIGNED`；`created_at DATETIME(6)`；`updated_at DATETIME(6)` | PK `id`；FK `assignment_id→experiment_task_assignments.id`、`user_id→users.id`；状态 `ACTIVE/CLOSED`；`context_json` 为授权对象白名单；唯一 `uq_conv_active(active_ctx_key, user_id)` 保证每用户每分配至多一个活跃会话；索引 `idx_conv_user_time(user_id, last_message_at)` |
| `assistant_messages` | `id BIGINT UNSIGNED`；`conversation_id BIGINT UNSIGNED`；`run_id BIGINT UNSIGNED`；`role VARCHAR(32)`；`content TEXT`；`token_count INT UNSIGNED`；`created_at DATETIME(6)` | PK `id`（消息游标）；FK `conversation_id→assistant_conversations.id`、可空 `run_id→agent_runs.id`；角色 `USER/ASSISTANT/SYSTEM/TOOL`；`content` 入库前脱敏，不含令牌/密钥/他人数据；只追加；索引 `idx_msg_conv_id(conversation_id, id)` 按会话顺序读取 |
| `tool_call_logs` | `id BIGINT UNSIGNED`；`run_id BIGINT UNSIGNED`；`assignment_id BIGINT UNSIGNED`；`tool_name VARCHAR(128)`；`high_risk_action VARCHAR(64)`；`risk_level VARCHAR(32)`；`approval_status VARCHAR(32)`；`status VARCHAR(32)`；`input_json JSON`；`output_summary TEXT`；`exit_code INT`；`approval_token_jti_hash CHAR(64)`；`approved_by_id BIGINT UNSIGNED`；`approved_at DATETIME(6)`；`denial_reason VARCHAR(512)`；`duration_ms INT UNSIGNED`；`trace_id VARCHAR(64)`；`created_at DATETIME(6)`；`updated_at DATETIME(6)` | PK `id`；FK `run_id→agent_runs.id`、`assignment_id→experiment_task_assignments.id`、可空 `approved_by_id→users.id`；`high_risk_action` `COMMAND_EXEC/FILE_WRITE/FILE_DELETE/DEPENDENCY_INSTALL/NETWORK_ACCESS`；风险 `LOW/MEDIUM/HIGH`；审批 `NOT_REQUIRED/PENDING/APPROVED/REJECTED/EXPIRED`；执行 `PENDING_APPROVAL/RUNNING/SUCCEEDED/FAILED/DENIED/BLOCKED`；`input_json` 脱敏，禁止拼接 Shell；索引 `idx_tool_run(run_id)`、`idx_tool_approval(approval_status, risk_level, created_at)`（待审批队列）、`idx_tool_assign(assignment_id)`、`idx_tool_trace(trace_id)` |

### 3.2 评测与模型调用表

| 表 | 字段（类型） | 约束/说明 |
|---|---|---|
| `evaluation_rules` | `id BIGINT UNSIGNED`；`template_version_id BIGINT UNSIGNED`；`rule_code VARCHAR(64)`；`rule_name VARCHAR(255)`；`rule_type VARCHAR(32)`；`rule_config JSON`；`is_mandatory TINYINT(1)`；`max_score DECIMAL(5,2)`；`weight DECIMAL(5,2)`；`timeout_sec INT UNSIGNED`；`sort_order INT UNSIGNED`；`is_enabled TINYINT(1)`；`created_at DATETIME(6)`；`updated_at DATETIME(6)` | PK `id`；FK `template_version_id→experiment_template_versions.id`；`rule_type` `COMMAND_EXIT_CODE/OUTPUT_MATCH/METRIC_THRESHOLD/FILE_EXISTS/SCRIPT`；唯一 `uq_evalrule_version_code(template_version_id, rule_code)`；索引 `idx_evalrule_version(template_version_id, is_enabled)` |
| `evaluation_jobs` | `id BIGINT UNSIGNED`；`assignment_id BIGINT UNSIGNED`；`report_version_id BIGINT UNSIGNED`；`template_version_id BIGINT UNSIGNED`；`trigger_source VARCHAR(32)`；`status VARCHAR(32)`；`passed TINYINT(1)`；`rule_total INT UNSIGNED`；`rule_passed INT UNSIGNED`；`total_score DECIMAL(5,2)`；`max_score DECIMAL(5,2)`；`idempotency_key VARCHAR(128)`；`attempt_no INT UNSIGNED`；`triggered_by_id BIGINT UNSIGNED`；`error_code VARCHAR(64)`；`error_message VARCHAR(512)`；`trace_id VARCHAR(64)`；`started_at DATETIME(6)`；`finished_at DATETIME(6)`；`created_at DATETIME(6)`；`updated_at DATETIME(6)` | PK `id`；FK `assignment_id→experiment_task_assignments.id`、可空 `report_version_id→experiment_report_versions.id`、`template_version_id→experiment_template_versions.id`、可空 `triggered_by_id→users.id`；`trigger_source` `SUBMIT/MANUAL_RETRY/SCHEDULED`；状态 `PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED`；唯一 `uq_evaljob_idem(idempotency_key)` 防重复触发；索引 `idx_evaljob_assign(assignment_id)`、`idx_evaljob_version(report_version_id, status)`、`idx_evaljob_status(status, created_at)` |
| `evaluation_results` | `id BIGINT UNSIGNED`；`job_id BIGINT UNSIGNED`；`assignment_id BIGINT UNSIGNED`；`report_version_id BIGINT UNSIGNED`；`rule_id BIGINT UNSIGNED`；`status VARCHAR(32)`；`passed TINYINT(1)`；`score DECIMAL(5,2)`；`output_summary TEXT`；`evidence_file_id BIGINT UNSIGNED`；`error_code VARCHAR(64)`；`started_at DATETIME(6)`；`finished_at DATETIME(6)`；`created_at DATETIME(6)` | PK `id`；FK `job_id→evaluation_jobs.id`（一次运行对多条规则父子关系）、`assignment_id→experiment_task_assignments.id`、可空 `report_version_id→experiment_report_versions.id`、`rule_id→evaluation_rules.id`、可空 `evidence_file_id→files.id`；状态 `PENDING/RUNNING/PASSED/FAILED/ERROR/SKIPPED`；`output_summary` 脱敏；只追加；索引 `idx_evalres_job(job_id, status)`、`idx_evalres_version(report_version_id, status)`、`idx_evalres_assign(assignment_id)`、`idx_evalres_rule(rule_id, status)` |
| `model_providers` | `id BIGINT UNSIGNED`；`provider_code VARCHAR(64)`；`provider_name VARCHAR(255)`；`provider_type VARCHAR(32)`；`base_url VARCHAR(512)`；`credential_ref VARCHAR(128)`；`capability_json JSON`；`quota_json JSON`；`is_enabled TINYINT(1)`；`health_status VARCHAR(32)`；`last_checked_at DATETIME(6)`；`updated_by_id BIGINT UNSIGNED`；`created_at DATETIME(6)`；`updated_at DATETIME(6)` | PK `id`；唯一 `uq_provider_code(provider_code)`；可空 FK `updated_by_id→users.id`；`provider_type` `OPENAI_COMPATIBLE/ANTHROPIC/AZURE_OPENAI/LOCAL`；健康 `UNKNOWN/HEALTHY/DEGRADED/DOWN`；`base_url` 仅服务端可见，`credential_ref` 只存密钥服务引用；停用不得删除历史调用记录；索引 `idx_provider_enabled(is_enabled, provider_type)` |
| `model_call_logs` | `id BIGINT UNSIGNED`；`call_type VARCHAR(32)`；`job_id BIGINT UNSIGNED`；`run_id BIGINT UNSIGNED`；`provider_id BIGINT UNSIGNED`；`model_name VARCHAR(128)`；`model_version VARCHAR(64)`；`status VARCHAR(32)`；`prompt_tokens INT UNSIGNED`；`completion_tokens INT UNSIGNED`；`total_tokens INT UNSIGNED`；`latency_ms INT UNSIGNED`；`error_code VARCHAR(64)`；`request_digest CHAR(64)`；`request_object_key VARCHAR(512)`；`response_digest CHAR(64)`；`response_object_key VARCHAR(512)`；`credential_ref VARCHAR(128)`；`trace_id VARCHAR(64)`；`created_at DATETIME(6)` | PK `id`；FK 可空 `job_id→evaluation_jobs.id`、可空 `run_id→agent_runs.id`、`provider_id→model_providers.id`；`call_type` `EVALUATION/AGENT_CHAT/EMBEDDING`（`EVALUATION` 时 `job_id` 非空、`AGENT_CHAT` 时 `run_id` 非空）；状态 `SUCCEEDED/FAILED/TIMEOUT/RATE_LIMITED`；摘要为 SHA-256，原文走对象存储引用；只追加；索引 `idx_modelcall_job(job_id)`、`idx_modelcall_run(run_id)`、`idx_modelcall_provider_time(provider_id, created_at)`、`idx_modelcall_trace(trace_id)` |

### 3.3 可靠性表

| 表 | 字段（类型） | 约束/说明 |
|---|---|---|
| `outbox_events` | `id BIGINT UNSIGNED`；`event_id CHAR(36)`；`event_type VARCHAR(64)`；`aggregate_type VARCHAR(64)`；`aggregate_id BIGINT UNSIGNED`；`assignment_id BIGINT UNSIGNED`；`instance_id BIGINT UNSIGNED`；`topic VARCHAR(128)`；`payload_json JSON`；`status VARCHAR(32)`；`attempt_count INT UNSIGNED`；`available_at DATETIME(6)`；`published_at DATETIME(6)`；`last_error VARCHAR(512)`；`trace_id VARCHAR(64)`；`created_at DATETIME(6)` | PK `id`（投递顺序）；唯一 `uq_outbox_event_id(event_id)` 消费者去重；`aggregate_type` `ASSIGNMENT/INSTANCE/REPORT/ARCHIVE/SESSION/QUOTA`；状态 `PENDING/PUBLISHED/FAILED/DEAD`；`attempt_count` 上限 10；`payload_json` 脱敏；只追加、无 `updated_at`；索引 `idx_outbox_status_time(status, available_at)`、`idx_outbox_aggregate(aggregate_type, aggregate_id)`、`idx_outbox_assignment(assignment_id)`、`idx_outbox_trace(trace_id)`（附件5 另列 `idx_outbox_status_avail(status, available_at)` 与 `idx_outbox_status_time` 同字段，属附件5 冗余索引，按附件5 原样保留） |
| `compensation_jobs` | `id BIGINT UNSIGNED`；`failure_stage VARCHAR(32)`；`target_type VARCHAR(64)`；`target_id BIGINT UNSIGNED`；`assignment_id BIGINT UNSIGNED`；`instance_id BIGINT UNSIGNED`；`idempotency_key VARCHAR(128)`；`status VARCHAR(32)`；`attempt_count INT UNSIGNED`；`max_attempts INT UNSIGNED`；`next_retry_at DATETIME(6)`；`last_error_code VARCHAR(64)`；`last_error_message VARCHAR(512)`；`payload_json JSON`；`resolved_by_id BIGINT UNSIGNED`；`resolution_note VARCHAR(512)`；`resolved_at DATETIME(6)`；`trace_id VARCHAR(64)`；`created_at DATETIME(6)`；`updated_at DATETIME(6)` | PK `id`；唯一 `uq_comp_idem(idempotency_key)`（人工重试同样幂等）；可空 FK `assignment_id→experiment_task_assignments.id`、`instance_id→experiment_instances.id`、`resolved_by_id→users.id`；`failure_stage` `PROVISIONING/ARCHIVING/ACCESS_REVOKE/DESTROYING/QUOTA_RELEASE/OUTBOX_PUBLISH`；`target_type` `INSTANCE/ASSIGNMENT/ARCHIVE/SESSION/QUOTA/OUTBOX_EVENT`；状态 `PENDING/RUNNING/SUCCEEDED/FAILED/MANUAL/RESOLVED`；索引 `idx_comp_status_stage(status, failure_stage, next_retry_at)`、`idx_comp_assignment(assignment_id)`、`idx_comp_instance(instance_id)`、`idx_comp_status_retry(status, next_retry_at)` |
| `notifications` | `id BIGINT UNSIGNED`；`user_id BIGINT UNSIGNED`；`notification_type VARCHAR(64)`；`title VARCHAR(255)`；`content VARCHAR(1024)`；`target_type VARCHAR(64)`；`target_id BIGINT UNSIGNED`；`action_url VARCHAR(512)`；`is_read TINYINT(1)`；`read_at DATETIME(6)`；`source_event_id CHAR(36)`；`created_at DATETIME(6)` | PK `id`；FK `user_id→users.id`；唯一 `uq_notif_source_event(source_event_id)` 消费去重；`target_type` `ASSIGNMENT/REPORT/ARCHIVE/TASK/INSTANCE`；`action_url` 相对路径，不含内部地址；索引 `idx_notif_user_read_time(user_id, is_read, created_at)` |
| `audit_logs` | `id BIGINT UNSIGNED`；`actor_user_id BIGINT UNSIGNED`；`actor_role_code VARCHAR(32)`；`action VARCHAR(64)`；`target_type VARCHAR(64)`；`target_id BIGINT UNSIGNED`；`assignment_id BIGINT UNSIGNED`；`instance_id BIGINT UNSIGNED`；`trace_id VARCHAR(64)`；`request_id VARCHAR(64)`；`idempotency_key VARCHAR(128)`；`result VARCHAR(32)`；`reason VARCHAR(512)`；`before_json JSON`；`after_json JSON`；`ip VARCHAR(64)`；`user_agent_hash CHAR(64)`；`occurred_at DATETIME(6)`；`created_at DATETIME(6)` | PK `id`；可空 FK `actor_user_id→users.id`、`assignment_id→experiment_task_assignments.id`、`instance_id→experiment_instances.id`；`action` 示例含 `AGENT_TOOL_APPROVE`；`target_type` `USER/TEMPLATE/TASK/ASSIGNMENT/INSTANCE/REPORT/ARCHIVE/SESSION/QUOTA/COMPENSATION`；`result` `SUCCESS/DENIED/FAILURE`；快照脱敏；只追加、无 `updated_at`；索引 `idx_audit_actor_time(actor_user_id, occurred_at)`、`idx_audit_target(target_type, target_id)`、`idx_audit_instance(instance_id)`、`idx_audit_action_time(action, occurred_at)`、`idx_audit_trace_time(trace_id, created_at)`、`idx_audit_assignment_time(assignment_id, created_at)` |

## 4. 状态、约束和索引

### 4.1 状态机

- **Agent 运行**：`PENDING -> RUNNING -> SUCCEEDED`；任意运行态可进入 `FAILED/CANCELLED`。数据库保存状态，合法性由服务层实现；每次状态变化写 `audit_logs`（`AGENT_TOOL_APPROVE` 等动作）与必要 `outbox_events`。
- **会话**：`ACTIVE -> CLOSED`；关闭后不可再投递消息，历史只读。
- **工具审批**：`approval_status` `NOT_REQUIRED`（低风险直接执行）→ `PENDING`（高风险等待）→ `APPROVED/REJECTED/EXPIRED`；`status` 同步 `PENDING_APPROVAL -> RUNNING -> SUCCEEDED/FAILED`，拒绝为 `DENIED`、参数非法为 `BLOCKED`。审批凭据一次性：`approval_token_jti_hash` 使用后即失效；`EXPIRED` 由超时（附件6 约定审批超时 5 分钟）扫描产生。
- **评测**：`evaluation_jobs.status` `PENDING -> RUNNING -> SUCCEEDED/FAILED/CANCELLED`；`evaluation_results.status` 逐规则 `PENDING/RUNNING/PASSED/FAILED/ERROR/SKIPPED`；`passed` 为强制规则是否全部通过的 AUTO 结论依据。
- **可靠性**：Outbox `PENDING -> PUBLISHED/FAILED`，超过最大尝试进入 `DEAD`；补偿 `PENDING -> RUNNING -> SUCCEEDED`，超限进入 `MANUAL -> RESOLVED`，不得无限重试。

### 4.2 必须建立的索引

| 表 | 索引 | 场景 |
|---|---|---|
| `agent_runs` | `idx_run_conv_time(conversation_id, created_at)`、`idx_run_assign(assignment_id)`、`idx_run_trace(trace_id)` | 会话时间线、任务归属、链路排查 |
| `assistant_conversations` | `uq_conv_active(active_ctx_key, user_id)`、`idx_conv_user_time(user_id, last_message_at)` | 每用户每分配一个活跃会话、会话列表 |
| `assistant_messages` | `idx_msg_conv_id(conversation_id, id)` | 按会话顺序读取消息 |
| `tool_call_logs` | `idx_tool_run(run_id)`、`idx_tool_approval(approval_status, risk_level, created_at)`、`idx_tool_assign(assignment_id)`、`idx_tool_trace(trace_id)` | 运行反查、待审批队列、安全审计 |
| `evaluation_rules` | `uq_evalrule_version_code(template_version_id, rule_code)`、`idx_evalrule_version(template_version_id, is_enabled)` | 版本规则唯一、启用检索 |
| `evaluation_jobs` | `uq_evaljob_idem(idempotency_key)`、`idx_evaljob_assign(assignment_id)`、`idx_evaljob_version(report_version_id, status)`、`idx_evaljob_status(status, created_at)` | 幂等、待处理队列 |
| `evaluation_results` | `idx_evalres_job(job_id, status)`、`idx_evalres_version(report_version_id, status)`、`idx_evalres_assign(assignment_id)`、`idx_evalres_rule(rule_id, status)` | 按运行/版本/规则汇总 |
| `model_providers` | `uq_provider_code(provider_code)`、`idx_provider_enabled(is_enabled, provider_type)` | 提供方唯一、启用检索 |
| `model_call_logs` | `idx_modelcall_job(job_id)`、`idx_modelcall_run(run_id)`、`idx_modelcall_provider_time(provider_id, created_at)`、`idx_modelcall_trace(trace_id)` | 评测/Agent 反查、用量检索 |
| `outbox_events` | `uq_outbox_event_id(event_id)`、`idx_outbox_status_time(status, available_at)`、`idx_outbox_aggregate(aggregate_type, aggregate_id)`、`idx_outbox_assignment(assignment_id)`、`idx_outbox_trace(trace_id)` | 投递扫描、消费去重、链路检索 |
| `compensation_jobs` | `uq_comp_idem(idempotency_key)`、`idx_comp_status_stage(status, failure_stage, next_retry_at)`、`idx_comp_assignment(assignment_id)`、`idx_comp_instance(instance_id)`、`idx_comp_status_retry(status, next_retry_at)` | 幂等重试、补偿扫描 |
| `notifications` | `uq_notif_source_event(source_event_id)`、`idx_notif_user_read_time(user_id, is_read, created_at)` | 消费去重、列表检索 |
| `audit_logs` | `idx_audit_actor_time(actor_user_id, occurred_at)`、`idx_audit_target(target_type, target_id)`、`idx_audit_instance(instance_id)`、`idx_audit_action_time(action, occurred_at)`、`idx_audit_trace_time(trace_id, created_at)`、`idx_audit_assignment_time(assignment_id, created_at)` | 审计查询、链路排查 |

### 4.3 关键字段规则

- `assistant_conversations.context_json` 必须为当前授权对象白名单；写入前由业务服务校验 ACTIVE 成员资格与资源归属，数据库不代替授权。
- `tool_call_logs` 的高风险动作必须存在 `approval_token_jti_hash`（一次性审批凭据）后才能进入 `RUNNING`；`approved_at` 与审批凭据使用时间一致。
- `evaluation_jobs.idempotency_key` 防重复触发，重试必须复用同一幂等键并递增 `attempt_no`；`evaluation_results` 按 `job_id` 汇总规则结论，不重复扣评测配额。
- `model_call_logs` 的 `request_digest/response_digest` 对脱敏后载荷计算 SHA-256；完整原文使用对象存储引用，任何字段不得存明文凭据。
- `audit_logs` 以 `occurred_at`（业务发生时间）与 `created_at`（入库时间）分离；`request_id`/`trace_id` 每次响应携带，跨模块联检。
- `error_message`、`payload_json`、`output_summary`、`before_json`、`after_json`、`input_json` 必须先脱敏；完整内容使用对象存储引用和 SHA-256 哈希。

## 5. 触发器、视图与存储过程（附件5 口径）

### 5.1 触发器（3 组设计条目 = 5 个 CREATE TRIGGER 对象）

附件5 共定义 5 个触发器对象，其中 **Agent 域直接相关 2 个（审计日志只追加）**，其余 3 个属报告/归档域（平台迁移统一执行，Agent 侧依赖其不变量）：

| 设计条目 | CREATE TRIGGER 对象 | 作用对象 | 说明 |
|---|---|---|---|
| 5.1 报告版本不可变 | `trg_report_version_immutable` | `experiment_report_versions` | 报告冻结后禁止修改正文/附件/快照/清单/提交时间；非 Agent 域 |
| 5.2 归档文件只追加 | `trg_archive_files_no_update`、`trg_archive_files_no_delete` | `experiment_archive_files` | 归档文件禁止更新/删除；非 Agent 域 |
| 5.3 审计日志只追加 | `trg_audit_log_no_update`、`trg_audit_log_no_delete` | `audit_logs` | **Agent 域相关**：审计日志禁止更新/删除，触发 `AUDIT_LOG_APPEND_ONLY` |

### 5.2 视图（4 个，Agent 侧使用但不属于 Agent 域）

- `v_assignment_overview`：任务分配聚合视图（用户/任务/模板/实例/报告/审核/归档），「我的实验」列表与教师看板读取。
- `v_pending_reviews`：待审核报告版本视图，**引用 `evaluation_jobs`（`auto_passed`）**，教师评分页与审核待办读取。
- `v_instance_provisioning`：实例与最近装载任务聚合视图，装载时间线/断线恢复读取。
- `v_archive_integrity`：归档状态与销毁门禁视图，留存治理读取。

### 5.3 存储过程（3 个，均非 Agent 域）

`sp_cleanup_expired_sessions`（会话过期）、`sp_reconcile_quota_usage`（配额对账）、`sp_expire_archives`（归档到期）；Agent 域不新增存储过程。

## 6. 生命周期和安全

1. 运行期保留会话、消息、运行、工具调用、模型调用、评测、事件和审计。
2. `assistant_messages`、`model_call_logs`、`tool_call_logs` 默认保留 7 天；评测结论、审计索引按团队策略保留。
3. 清理顺序：先确认归档成功（`v_archive_integrity.destroy_ready=1`），再删除 MinIO 详细对象，最后删除或匿名化数据库明细；`audit_logs` 只追加，不做物理删除。
4. 发生申诉、调查或合规保留时，生命周期服务必须支持冻结清理；冻结状态不放在 Agent 表状态中，使用外部生命周期策略 ID 或接口控制。
5. 禁止在任何字段保存明文密码、API Key、Token、Docker Socket、宿主机路径或跨实例文件路径；`approval_token_jti_hash` 只存 JTI 摘要。

## 7. 建表顺序与验收依据

- SQL 按「`model_providers` -> `agent_runs`/`assistant_conversations`/`assistant_messages`/`tool_call_logs` -> `evaluation_rules`/`evaluation_jobs`/`evaluation_results` -> `model_call_logs` -> `outbox_events`/`compensation_jobs`/`notifications`/`audit_logs`」的依赖顺序执行；平台主表（`users`、`experiment_task_assignments`、`experiment_template_versions`、`experiment_instances`、`experiment_report_versions`、`files`）由平台迁移先行建立。
- ER 图表达库内物理外键关系；平台主表以逻辑实体标注，不重复建模。
- 验收至少覆盖：会话活跃唯一约束、消息只追加、高风险工具审批状态机（PENDING 不得执行、拒绝不得 RUNNING）、审批凭据一次性、评测幂等防重、模型调用按 `call_type` 二选一、审计只追加触发器、跨实例查询隔离、脱敏与对象引用、链路（`trace_id`）可联检。
- 本文、`DESIGN/SQL/AGENT_DB.sql`、`DESIGN/ER/AGENT_DB.mmd` 与附件5 v1.0 的表名、字段名、索引名、状态值和外键关系必须保持一致；任何变更先更新附件5 与 04 章，再同步本文、SQL 与 ER。
