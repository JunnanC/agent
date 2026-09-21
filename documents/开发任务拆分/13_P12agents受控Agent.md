# P12 agents 受控 Agent

## 目标

建设课程级 Agent 平台：教师可配置版本化知识库、模式、提示词、模型路由、预算、工具和评测门禁；学生获得有引用的课程问答、循序提示、诊断、报告辅导和受控工作区协助。

## 后端范围

- 初始 schema 覆盖 course profile、knowledge base/source/source version、ingestion run、prompt template/version、session/message、retrieval trace/citation、tool policy/call/state/approval、eval suite/case/run/result 和 session feedback。
- `CourseAgentProfile` 状态为 DRAFT → EVALUATING → ACTIVE → RETIRED，固定 model route、prompt、knowledge、tool policy、模式、预算和生效时间；历史会话不随配置更新漂移。
- 知识源可来自已发布课程资料、实验手册、教师 FAQ 和受控静态资料；MinIO 保存原文，MySQL 保存 source/version/digest/ACL/解析事实。
- 实现可替换 `KnowledgeRetriever` 接口和关键词基线；向量/混合实现经选型后接入。索引是可重建派生数据，每次检索前后均重验 course/source version/audience/task ACL。
- 回答保存 retrieval trace 和 citation；`KNOWLEDGE_QA` 必须返回当前用户可访问引用，无可靠来源时降级为检索候选/明确不确定，不伪造来源。
- 模式完整实现：`KNOWLEDGE_QA`、`SOCRATIC_HINT`、`DEBUG_ASSIST`、`REPORT_COACH`、`WORKSPACE_ASSIST`；受保护实验不得直接泄露最终答案。
- AgentSession 绑定 student/course/enrollment/profile 及可选 task；任务型模式必须绑定有效 task。上下文只含已发布资料、冻结模板/手册、本人工作区摘要和报告草稿。
- LOW 只读工具自动执行；MEDIUM 按策略确认；HIGH 逐次人工审批；FORBIDDEN 永久拒绝。
- 工具 schema、风险、allowlist、沙箱、网络、超时、输出上限和脱敏规则版本化；执行端再次校验 session/task/workspace capability/approval，参数 digest 变化后重新审批。
- 模型网关支持平台批准路由、fallback、超时、token/频率/并发/检索/工具配额及课程预算；模型不可用时只允许安全降级，不绕过审批执行工具。
- 平台强制评测覆盖跨课程越权、提示注入、敏感数据、引用、无来源降级、拒答、工具安全、延迟和成本；教师可增加课程题例但不能删除强制用例。
- EvalRun 固定全部版本组合，未达阈值 profile 不能 ACTIVE；相关模型、提示词、知识切分或工具策略变化触发重新评测。
- Agent message、retrieval/citation、tool call、approval 只追加；执行状态使用独立投影。用户反馈和教师标记进入待分析队列，不自动成为训练数据。
- 为课程复制 job 注册 Agent 配置复制处理器；只复制选定知识源引用策略、提示词和 profile 草稿为全新版本，必须重新摄取和评测后才能激活。

## 前端范围

- user-web：课程/任务 Agent 面板、模式切换、流式/异步消息、可访问引用、无来源降级、工具审批、反馈、失败/限流/trace；报告建议需学生确认才写入草稿。
- teacher-web：课程 Agent profile、知识源与摄取状态、提示词版本、允许模式/工具/预算、课程评测题、评测结果、反馈处置和课程聚合分析；不能浏览学生完整私密对话。
- admin-web：模型路由、fallback、平台提示词/工具策略、强制评测套件、评测运行、调用/引用/拒绝/成本趋势和安全告警。

## 测试与验收

- Agent 不能检索其他学生、教师私有备注、管理审计、未发布资料或其他课程；伪造索引结果仍被后置 ACL 拒绝。
- 知识源新版本触发新索引且历史回答仍指向原版本；删除派生索引后可由 MySQL/MinIO 重建。
- 有来源回答包含可访问 citation，无可靠来源不编造引用；引用资产撤权后下载被拒绝。
- 提示词注入不能提升工具权限；执行端再次校验 scope、capability 和 approval。
- HIGH 工具无审批永远不执行；撤销、终态、退课和停用立即阻断新调用。
- profile 未通过平台和课程评测不能激活；版本变化使旧门禁结果失效。
- token/频率/并发/检索/工具/成本配额准确，消息/引用/调用/审批只追加且可按 trace 查询。
- 模型超时、fallback、重复回调、网关失败、长输出截断和敏感内容脱敏通过。
- 教师只能查看反馈和聚合指标；报告辅助不会自动提交，任何 Agent 输出都不能改变审核或任务状态。

## 不做

- 不让 Agent 修改审核决定、任务状态、实例、配额、网络策略或跨任务文件。
- 不用 MongoDB 日志保存知识原文、完整提示词或教学分析事实；不将用户反馈未经治理直接用于训练。

## 出口

教师可完成“知识源 → 版本化配置 → 固定版本评测 → 激活”的闭环；学生获得可引用、可反馈、可降级的受控 Agent，高风险操作有逐次审批和完整审计。
