-- ============================================================================
-- Agent 域数据模型建表脚本（v1.0 同步版）
-- 权威依据：附件5：数据库设计文档.docx v1.0（2026-09-14）
-- 库：agent_virtual_lab（与平台业务表同库，非独立 agent 库）
-- 依赖：users、experiment_task_assignments、experiment_template_versions、
--       experiment_instances、experiment_report_versions、files 由平台迁移先行建立
-- 说明：本脚本只含 Agent 域 13 张表 + 审计日志只追加触发器；
--       触发器其余 3 个对象（报告版本不可变/归档文件只追加）与 3 个存储过程
--       属平台迁移，见平台 v1.0 迁移基线，不在此重复。
-- ============================================================================

CREATE DATABASE IF NOT EXISTS agent_virtual_lab
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;
USE agent_virtual_lab;

-- ----------------------------------------------------------------------------
-- 3.1 Agent 业务表
-- ----------------------------------------------------------------------------

-- Agent 运行表
CREATE TABLE agent_runs (
    id                 BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    conversation_id    BIGINT UNSIGNED NOT NULL,
    assignment_id      BIGINT UNSIGNED NOT NULL,
    user_id            BIGINT UNSIGNED NOT NULL,
    status             VARCHAR(32)  NOT NULL,
    model_name         VARCHAR(128) NULL,
    prompt_tokens      INT UNSIGNED NOT NULL DEFAULT 0,
    completion_tokens  INT UNSIGNED NOT NULL DEFAULT 0,
    tool_call_count    INT UNSIGNED NOT NULL DEFAULT 0,
    latency_ms         INT UNSIGNED NULL,
    error_code         VARCHAR(64)  NULL,
    error_message      VARCHAR(512) NULL,
    trace_id           VARCHAR(64)  NULL,
    started_at         DATETIME(6)  NULL,
    finished_at        DATETIME(6)  NULL,
    created_at         DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_run_conversation FOREIGN KEY (conversation_id)
        REFERENCES assistant_conversations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_run_assignment FOREIGN KEY (assignment_id)
        REFERENCES experiment_task_assignments (id) ON DELETE RESTRICT,
    CONSTRAINT fk_run_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_run_status CHECK (status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')),
    KEY idx_run_conv_time (conversation_id, created_at),
    KEY idx_run_assign (assignment_id),
    KEY idx_run_trace (trace_id)
) ENGINE=InnoDB COMMENT='Agent 运行表';

-- Agent 会话表
CREATE TABLE assistant_conversations (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    assignment_id    BIGINT UNSIGNED NOT NULL,
    user_id          BIGINT UNSIGNED NOT NULL,
    title            VARCHAR(255) NULL,
    status           VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE',
    context_json     JSON         NOT NULL,
    last_message_at  DATETIME(6)  NULL,
    active_ctx_key   BIGINT UNSIGNED NULL,
    created_at       DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at       DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_conv_assignment FOREIGN KEY (assignment_id)
        REFERENCES experiment_task_assignments (id) ON DELETE RESTRICT,
    CONSTRAINT fk_conv_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_conv_status CHECK (status IN ('ACTIVE','CLOSED')),
    UNIQUE KEY uq_conv_active (active_ctx_key, user_id),
    KEY idx_conv_user_time (user_id, last_message_at)
) ENGINE=InnoDB COMMENT='Agent 会话表';

-- Agent 消息表（只追加；主键即消息游标）
CREATE TABLE assistant_messages (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    conversation_id BIGINT UNSIGNED NOT NULL,
    run_id          BIGINT UNSIGNED NULL,
    role            VARCHAR(32)  NOT NULL,
    content         TEXT         NOT NULL,
    token_count     INT UNSIGNED NOT NULL DEFAULT 0,
    created_at      DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_msg_conversation FOREIGN KEY (conversation_id)
        REFERENCES assistant_conversations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_msg_run FOREIGN KEY (run_id)
        REFERENCES agent_runs (id) ON DELETE RESTRICT,
    CONSTRAINT ck_msg_role CHECK (role IN ('USER','ASSISTANT','SYSTEM','TOOL')),
    KEY idx_msg_conv_id (conversation_id, id)
) ENGINE=InnoDB COMMENT='Agent 消息表';

-- Agent 工具调用与审批记录表
CREATE TABLE tool_call_logs (
    id                   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    run_id               BIGINT UNSIGNED NOT NULL,
    assignment_id        BIGINT UNSIGNED NOT NULL,
    tool_name            VARCHAR(128) NOT NULL,
    high_risk_action     VARCHAR(64)  NULL,
    risk_level           VARCHAR(32)  NOT NULL,
    approval_status      VARCHAR(32)  NOT NULL,
    status               VARCHAR(32)  NOT NULL,
    input_json           JSON         NULL,
    output_summary       TEXT         NULL,
    exit_code            INT          NULL,
    approval_token_jti_hash CHAR(64)  NULL,
    approved_by_id       BIGINT UNSIGNED NULL,
    approved_at          DATETIME(6)  NULL,
    denial_reason        VARCHAR(512) NULL,
    duration_ms          INT UNSIGNED NULL,
    trace_id             VARCHAR(64)  NULL,
    created_at           DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at           DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_tool_run FOREIGN KEY (run_id)
        REFERENCES agent_runs (id) ON DELETE RESTRICT,
    CONSTRAINT fk_tool_assignment FOREIGN KEY (assignment_id)
        REFERENCES experiment_task_assignments (id) ON DELETE RESTRICT,
    CONSTRAINT fk_tool_approver FOREIGN KEY (approved_by_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_tool_risk CHECK (risk_level IN ('LOW','MEDIUM','HIGH')),
    CONSTRAINT ck_tool_approval_status CHECK (approval_status IN ('NOT_REQUIRED','PENDING','APPROVED','REJECTED','EXPIRED')),
    CONSTRAINT ck_tool_status CHECK (status IN ('PENDING_APPROVAL','RUNNING','SUCCEEDED','FAILED','DENIED','BLOCKED')),
    KEY idx_tool_run (run_id),
    KEY idx_tool_approval (approval_status, risk_level, created_at),
    KEY idx_tool_assign (assignment_id),
    KEY idx_tool_trace (trace_id)
) ENGINE=InnoDB COMMENT='Agent 工具调用与审批记录表';

-- ----------------------------------------------------------------------------
-- 3.2 评测与模型调用表
-- ----------------------------------------------------------------------------

-- 评测规则表（随模板版本冻结）
CREATE TABLE evaluation_rules (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    template_version_id BIGINT UNSIGNED NOT NULL,
    rule_code           VARCHAR(64)  NOT NULL,
    rule_name           VARCHAR(255) NOT NULL,
    rule_type           VARCHAR(32)  NOT NULL,
    rule_config         JSON         NOT NULL,
    is_mandatory        TINYINT(1)   NOT NULL DEFAULT 0,
    max_score           DECIMAL(5,2) NOT NULL DEFAULT 0,
    weight              DECIMAL(5,2) NOT NULL DEFAULT 0,
    timeout_sec         INT UNSIGNED NOT NULL DEFAULT 30,
    sort_order          INT UNSIGNED NOT NULL DEFAULT 0,
    is_enabled          TINYINT(1)   NOT NULL DEFAULT 1,
    created_at          DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at          DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_evalrule_template_version FOREIGN KEY (template_version_id)
        REFERENCES experiment_template_versions (id) ON DELETE RESTRICT,
    CONSTRAINT ck_evalrule_type CHECK (rule_type IN ('COMMAND_EXIT_CODE','OUTPUT_MATCH','METRIC_THRESHOLD','FILE_EXISTS','SCRIPT')),
    UNIQUE KEY uq_evalrule_version_code (template_version_id, rule_code),
    KEY idx_evalrule_version (template_version_id, is_enabled)
) ENGINE=InnoDB COMMENT='评测规则表';

-- 评测任务表
CREATE TABLE evaluation_jobs (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    assignment_id       BIGINT UNSIGNED NOT NULL,
    report_version_id   BIGINT UNSIGNED NULL,
    template_version_id BIGINT UNSIGNED NOT NULL,
    trigger_source      VARCHAR(32)  NOT NULL,
    status              VARCHAR(32)  NOT NULL,
    passed              TINYINT(1)   NULL,
    rule_total          INT UNSIGNED NOT NULL DEFAULT 0,
    rule_passed         INT UNSIGNED NOT NULL DEFAULT 0,
    total_score         DECIMAL(5,2) NULL,
    max_score           DECIMAL(5,2) NULL,
    idempotency_key     VARCHAR(128) NOT NULL,
    attempt_no          INT UNSIGNED NOT NULL DEFAULT 1,
    triggered_by_id     BIGINT UNSIGNED NULL,
    error_code          VARCHAR(64)  NULL,
    error_message       VARCHAR(512) NULL,
    trace_id            VARCHAR(64)  NULL,
    started_at          DATETIME(6)  NULL,
    finished_at         DATETIME(6)  NULL,
    created_at          DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at          DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_evaljob_assignment FOREIGN KEY (assignment_id)
        REFERENCES experiment_task_assignments (id) ON DELETE RESTRICT,
    CONSTRAINT fk_evaljob_report_version FOREIGN KEY (report_version_id)
        REFERENCES experiment_report_versions (id) ON DELETE RESTRICT,
    CONSTRAINT fk_evaljob_template_version FOREIGN KEY (template_version_id)
        REFERENCES experiment_template_versions (id) ON DELETE RESTRICT,
    CONSTRAINT fk_evaljob_triggered_by FOREIGN KEY (triggered_by_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_evaljob_trigger CHECK (trigger_source IN ('SUBMIT','MANUAL_RETRY','SCHEDULED')),
    CONSTRAINT ck_evaljob_status CHECK (status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')),
    UNIQUE KEY uq_evaljob_idem (idempotency_key),
    KEY idx_evaljob_assign (assignment_id),
    KEY idx_evaljob_version (report_version_id, status),
    KEY idx_evaljob_status (status, created_at)
) ENGINE=InnoDB COMMENT='评测任务表';

-- 评测结果表（一次运行对多条规则，父子关系）
CREATE TABLE evaluation_results (
    id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    job_id            BIGINT UNSIGNED NOT NULL,
    assignment_id     BIGINT UNSIGNED NOT NULL,
    report_version_id BIGINT UNSIGNED NULL,
    rule_id           BIGINT UNSIGNED NOT NULL,
    status            VARCHAR(32)  NOT NULL,
    passed            TINYINT(1)   NULL,
    score             DECIMAL(5,2) NULL,
    output_summary    TEXT         NULL,
    evidence_file_id  BIGINT UNSIGNED NULL,
    error_code        VARCHAR(64)  NULL,
    started_at        DATETIME(6)  NULL,
    finished_at       DATETIME(6)  NULL,
    created_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_evalres_job FOREIGN KEY (job_id)
        REFERENCES evaluation_jobs (id) ON DELETE RESTRICT,
    CONSTRAINT fk_evalres_assignment FOREIGN KEY (assignment_id)
        REFERENCES experiment_task_assignments (id) ON DELETE RESTRICT,
    CONSTRAINT fk_evalres_report_version FOREIGN KEY (report_version_id)
        REFERENCES experiment_report_versions (id) ON DELETE RESTRICT,
    CONSTRAINT fk_evalres_rule FOREIGN KEY (rule_id)
        REFERENCES evaluation_rules (id) ON DELETE RESTRICT,
    CONSTRAINT fk_evalres_evidence FOREIGN KEY (evidence_file_id)
        REFERENCES files (id) ON DELETE RESTRICT,
    CONSTRAINT ck_evalres_status CHECK (status IN ('PENDING','RUNNING','PASSED','FAILED','ERROR','SKIPPED')),
    KEY idx_evalres_job (job_id, status),
    KEY idx_evalres_version (report_version_id, status),
    KEY idx_evalres_assign (assignment_id),
    KEY idx_evalres_rule (rule_id, status)
) ENGINE=InnoDB COMMENT='评测结果表';

-- 模型提供方表
CREATE TABLE model_providers (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    provider_code    VARCHAR(64)  NOT NULL,
    provider_name    VARCHAR(255) NOT NULL,
    provider_type    VARCHAR(32)  NOT NULL,
    base_url         VARCHAR(512) NULL,
    credential_ref   VARCHAR(128) NULL,
    capability_json  JSON         NOT NULL,
    quota_json       JSON         NULL,
    is_enabled       TINYINT(1)   NOT NULL DEFAULT 1,
    health_status    VARCHAR(32)  NOT NULL DEFAULT 'UNKNOWN',
    last_checked_at  DATETIME(6)  NULL,
    updated_by_id    BIGINT UNSIGNED NULL,
    created_at       DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at       DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_provider_updated_by FOREIGN KEY (updated_by_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_provider_type CHECK (provider_type IN ('OPENAI_COMPATIBLE','ANTHROPIC','AZURE_OPENAI','LOCAL')),
    CONSTRAINT ck_provider_health CHECK (health_status IN ('UNKNOWN','HEALTHY','DEGRADED','DOWN')),
    UNIQUE KEY uq_provider_code (provider_code),
    KEY idx_provider_enabled (is_enabled, provider_type)
) ENGINE=InnoDB COMMENT='模型提供方表';

-- 模型调用日志表（只追加；Agent 与评测两侧统一记账）
CREATE TABLE model_call_logs (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    call_type           VARCHAR(32)  NOT NULL,
    job_id              BIGINT UNSIGNED NULL,
    run_id              BIGINT UNSIGNED NULL,
    provider_id         BIGINT UNSIGNED NOT NULL,
    model_name          VARCHAR(128) NOT NULL,
    model_version       VARCHAR(64)  NULL,
    status              VARCHAR(32)  NOT NULL,
    prompt_tokens       INT UNSIGNED NULL,
    completion_tokens   INT UNSIGNED NULL,
    total_tokens        INT UNSIGNED NULL,
    latency_ms          INT UNSIGNED NULL,
    error_code          VARCHAR(64)  NULL,
    request_digest      CHAR(64)     NULL,
    request_object_key  VARCHAR(512) NULL,
    response_digest     CHAR(64)     NULL,
    response_object_key VARCHAR(512) NULL,
    credential_ref      VARCHAR(128) NULL,
    trace_id            VARCHAR(64)  NULL,
    created_at          DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_modelcall_job FOREIGN KEY (job_id)
        REFERENCES evaluation_jobs (id) ON DELETE RESTRICT,
    CONSTRAINT fk_modelcall_run FOREIGN KEY (run_id)
        REFERENCES agent_runs (id) ON DELETE RESTRICT,
    CONSTRAINT fk_modelcall_provider FOREIGN KEY (provider_id)
        REFERENCES model_providers (id) ON DELETE RESTRICT,
    CONSTRAINT ck_modelcall_type CHECK (call_type IN ('EVALUATION','AGENT_CHAT','EMBEDDING')),
    CONSTRAINT ck_modelcall_status CHECK (status IN ('SUCCEEDED','FAILED','TIMEOUT','RATE_LIMITED')),
    KEY idx_modelcall_job (job_id),
    KEY idx_modelcall_run (run_id),
    KEY idx_modelcall_provider_time (provider_id, created_at),
    KEY idx_modelcall_trace (trace_id)
) ENGINE=InnoDB COMMENT='模型调用日志表';

-- ----------------------------------------------------------------------------
-- 3.3 可靠性表
-- ----------------------------------------------------------------------------

-- Outbox 事件表（只追加）
CREATE TABLE outbox_events (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event_id       CHAR(36)     NOT NULL,
    event_type     VARCHAR(64)  NOT NULL,
    aggregate_type VARCHAR(64)  NOT NULL,
    aggregate_id   BIGINT UNSIGNED NOT NULL,
    assignment_id  BIGINT UNSIGNED NULL,
    instance_id    BIGINT UNSIGNED NULL,
    topic          VARCHAR(128) NOT NULL,
    payload_json   JSON         NOT NULL,
    status         VARCHAR(32)  NOT NULL DEFAULT 'PENDING',
    attempt_count  INT UNSIGNED NOT NULL DEFAULT 0,
    available_at   DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    published_at   DATETIME(6)  NULL,
    last_error     VARCHAR(512) NULL,
    trace_id       VARCHAR(64)  NULL,
    created_at     DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT ck_outbox_status CHECK (status IN ('PENDING','PUBLISHED','FAILED','DEAD')),
    UNIQUE KEY uq_outbox_event_id (event_id),
    KEY idx_outbox_status_time (status, available_at),
    KEY idx_outbox_aggregate (aggregate_type, aggregate_id),
    KEY idx_outbox_assignment (assignment_id),
    KEY idx_outbox_trace (trace_id),
    KEY idx_outbox_status_avail (status, available_at)
) ENGINE=InnoDB COMMENT='Outbox 事件表（只追加）';

-- 补偿任务表
CREATE TABLE compensation_jobs (
    id                 BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    failure_stage      VARCHAR(32)  NOT NULL,
    target_type        VARCHAR(64)  NOT NULL,
    target_id          BIGINT UNSIGNED NOT NULL,
    assignment_id      BIGINT UNSIGNED NULL,
    instance_id        BIGINT UNSIGNED NULL,
    idempotency_key    VARCHAR(128) NOT NULL,
    status             VARCHAR(32)  NOT NULL,
    attempt_count      INT UNSIGNED NOT NULL DEFAULT 0,
    max_attempts       INT UNSIGNED NOT NULL,
    next_retry_at      DATETIME(6)  NULL,
    last_error_code    VARCHAR(64)  NULL,
    last_error_message VARCHAR(512) NULL,
    payload_json       JSON         NULL,
    resolved_by_id     BIGINT UNSIGNED NULL,
    resolution_note    VARCHAR(512) NULL,
    resolved_at        DATETIME(6)  NULL,
    trace_id           VARCHAR(64)  NULL,
    created_at         DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at         DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_comp_assignment FOREIGN KEY (assignment_id)
        REFERENCES experiment_task_assignments (id) ON DELETE RESTRICT,
    CONSTRAINT fk_comp_instance FOREIGN KEY (instance_id)
        REFERENCES experiment_instances (id) ON DELETE RESTRICT,
    CONSTRAINT fk_comp_resolved_by FOREIGN KEY (resolved_by_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_comp_status CHECK (status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','MANUAL','RESOLVED')),
    UNIQUE KEY uq_comp_idem (idempotency_key),
    KEY idx_comp_status_stage (status, failure_stage, next_retry_at),
    KEY idx_comp_assignment (assignment_id),
    KEY idx_comp_instance (instance_id),
    KEY idx_comp_status_retry (status, next_retry_at)
) ENGINE=InnoDB COMMENT='补偿任务表';

-- 通知表
CREATE TABLE notifications (
    id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id           BIGINT UNSIGNED NOT NULL,
    notification_type VARCHAR(64)  NOT NULL,
    title             VARCHAR(255) NOT NULL,
    content           VARCHAR(1024) NULL,
    target_type       VARCHAR(64)  NULL,
    target_id         BIGINT UNSIGNED NULL,
    action_url        VARCHAR(512) NULL,
    is_read           TINYINT(1)   NOT NULL DEFAULT 0,
    read_at           DATETIME(6)  NULL,
    source_event_id   CHAR(36)     NULL,
    created_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    UNIQUE KEY uq_notif_source_event (source_event_id),
    KEY idx_notif_user_read_time (user_id, is_read, created_at)
) ENGINE=InnoDB COMMENT='通知表';

-- 审计日志表（只追加）
CREATE TABLE audit_logs (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    actor_user_id   BIGINT UNSIGNED NULL,
    actor_role_code VARCHAR(32)  NULL,
    action          VARCHAR(64)  NOT NULL,
    target_type     VARCHAR(64)  NOT NULL,
    target_id       BIGINT UNSIGNED NULL,
    assignment_id   BIGINT UNSIGNED NULL,
    instance_id     BIGINT UNSIGNED NULL,
    trace_id        VARCHAR(64)  NULL,
    request_id      VARCHAR(64)  NULL,
    idempotency_key VARCHAR(128) NULL,
    result          VARCHAR(32)  NOT NULL,
    reason          VARCHAR(512) NULL,
    before_json     JSON         NULL,
    after_json      JSON         NULL,
    ip              VARCHAR(64)  NULL,
    user_agent_hash CHAR(64)     NULL,
    occurred_at     DATETIME(6)  NOT NULL,
    created_at      DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_audit_actor FOREIGN KEY (actor_user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_audit_assignment FOREIGN KEY (assignment_id)
        REFERENCES experiment_task_assignments (id) ON DELETE RESTRICT,
    CONSTRAINT fk_audit_instance FOREIGN KEY (instance_id)
        REFERENCES experiment_instances (id) ON DELETE RESTRICT,
    CONSTRAINT ck_audit_result CHECK (result IN ('SUCCESS','DENIED','FAILURE')),
    KEY idx_audit_actor_time (actor_user_id, occurred_at),
    KEY idx_audit_target (target_type, target_id),
    KEY idx_audit_instance (instance_id),
    KEY idx_audit_action_time (action, occurred_at),
    KEY idx_audit_trace_time (trace_id, created_at),
    KEY idx_audit_assignment_time (assignment_id, created_at)
) ENGINE=InnoDB COMMENT='审计日志表（只追加）';

-- ----------------------------------------------------------------------------
-- 触发器：审计日志只追加（附件5 设计条目 5.3，Agent 域相关）
-- 注意：audit_logs 无 updated_at；BEFORE UPDATE 触发器在无此列时仍可阻止更新
-- ----------------------------------------------------------------------------
DELIMITER $$
CREATE TRIGGER trg_audit_log_no_update
BEFORE UPDATE ON audit_logs
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'AUDIT_LOG_APPEND_ONLY';
END$$
CREATE TRIGGER trg_audit_log_no_delete
BEFORE DELETE ON audit_logs
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'AUDIT_LOG_APPEND_ONLY';
END$$
DELIMITER ;

-- ----------------------------------------------------------------------------
-- 其余触发器与存储过程（非 Agent 域，由平台 v1.0 迁移基线统一执行）：
--   trg_report_version_immutable（报告版本不可变）
--   trg_archive_files_no_update / trg_archive_files_no_delete（归档文件只追加）
--   sp_cleanup_expired_sessions / sp_reconcile_quota_usage / sp_expire_archives
-- ----------------------------------------------------------------------------
