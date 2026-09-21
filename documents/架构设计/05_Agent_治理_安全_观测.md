# 05 Agent、治理、安全与观测

> 上游：`00`～`04`  
> 状态：目标治理设计

## 一、Agent 子系统

Agent 服务于课程学习和个人实验任务，提供课程资料问答、苏格拉底式提示、错误诊断、实验步骤解释、报告辅导和受控工作区工具。Agent 不是教师审核者、平台管理员、成绩决定者或环境自由配置器。

### 课程 Agent 配置

教师可为本课程创建 `CourseAgentProfile`，选择平台批准的模型/路由策略、交互模式、知识库版本、允许工具集、单次/每日预算和生效时间。教师只能填写平台开放的课程指令区，不能覆盖平台安全提示词、工具风险等级、数据边界和禁用能力。

配置采用 DRAFT → EVALUATING → ACTIVE → RETIRED；激活前必须通过平台基线评测和课程自定义评测。正在进行的会话绑定 profile/prompt/knowledge 版本，配置更新不静默改变历史会话。

### 上下文隔离

每个 `AgentSession` 绑定：

```text
student_id + course_id + enrollment_id + course_profile_version
+ mode + agent_definition_id + task_id(NULLABLE)
```

仅 `KNOWLEDGE_QA` 允许 `task_id=NULL`，此时上下文只能包含该课程已发布且当前选课可见的资料。`SOCRATIC_HINT`、`DEBUG_ASSIST`、`REPORT_COACH`、`WORKSPACE_ASSIST` 必须绑定本人有效 task，才可加入该任务的冻结模板/实验手册、允许的工作区摘要、本人报告草稿和必要错误信息。不得检索同课程其他学生、教师私有备注、管理端审计、未发布资料或其他课程资料。每次检索都按 course/source version/audience 以及可选 task scope 重验权限，不能仅信任向量索引返回结果。

### 知识库与检索引用

- 知识源可以来自课程资料、实验手册、教师发布的 FAQ 和受控外部静态资料；原文保存在 MinIO，MySQL 保存 source/version/digest/权限/解析状态。
- `KnowledgeRetriever` 支持关键词、向量或混合检索；向量索引是可重建派生数据，不是事实源。具体引擎在 P12 选型评审中冻结。
- 每次回答保存 retrieval trace：查询摘要、source version、片段引用、排序分数、过滤原因和模型/提示词版本。
- 知识问答必须输出用户当前可访问的引用；找不到可靠来源时明确说明不确定，不能生成伪造引用。
- 知识源更新生成新版本并触发重新索引，历史回答仍指向原 source version。

### 交互模式

| 模式 | 行为约束 |
|---|---|
| `KNOWLEDGE_QA` | 基于课程知识库回答并强制引用 |
| `SOCRATIC_HINT` | 逐步提示，不直接给出受保护实验的最终答案 |
| `DEBUG_ASSIST` | 读取允许的错误/环境摘要，给出诊断和可验证步骤 |
| `REPORT_COACH` | 提供结构、表达和缺项建议，学生确认后才能写入草稿 |
| `WORKSPACE_ASSIST` | 仅通过受控工具执行，遵守审批和工作区 capability |

### 工具策略

| 风险 | 示例 | 策略 |
|---|---|---|
| LOW | 读取手册、解释任务、读取允许的只读日志 | 可自动执行，完整审计 |
| MEDIUM | 在任务工作区生成文件、运行只读诊断 | 明确展示影响，可按课程策略要求确认 |
| HIGH | 修改/删除文件、运行命令、安装依赖、联网 | 默认拒绝；开放时必须逐次人工批准 |
| FORBIDDEN | 修改任务/审核状态、访问其他学生、管理实例/配额 | 永久禁止，不提供工具 |

提示词不能提升工具权限。工具执行端再次校验 session、task、student、workspace capability 和审批事实；模型输出不是授权令牌。

工具 schema、风险等级、参数脱敏规则和结果上限都由平台版本化。高风险审批绑定具体 tool_call、参数 digest、有效期和当前工作区版本；修改参数必须重新审批。命令执行使用 allowlist/沙箱/超时/输出限额，网络访问必须命中平台白名单。

### 模型路由、预算与降级

- 平台管理员配置可用模型、地区、敏感数据策略、超时、fallback 和成本单价；课程教师只能在批准集合中选择。
- 路由顺序依据任务模式、上下文大小、课程预算和健康状态，fallback 必须保留原 trace 并重新执行输出安全检查。
- 平台、课程、用户三级限制 token、请求频率、并发、知识检索量和工具调用量；预算不足返回明确错误，不静默切换到不合规模型。
- 模型不可用时知识问答可降级为检索结果列表，工具执行不可绕过模型/审批链路直接运行。

### 评测与发布门禁

- 平台维护安全基线套件：跨课程越权、提示注入、敏感数据、无来源回答、工具越权、拒答和成本上限。
- 教师可增加课程题例和期望引用，但不能删除平台强制用例。
- EvalRun 固定 model/profile/prompt/knowledge/tool-policy 版本，保存准确性、引用覆盖、拒答、工具安全、延迟和成本结果。
- 评测未达阈值的配置不能激活；模型、提示词、知识切分或工具策略更新必须重跑受影响套件。
- 用户反馈和教师标记进入待分析队列，不直接成为训练数据；任何再利用需单独脱敏和治理。

### 数据保存

- 不保存完整敏感上下文副本；保存引用、digest、脱敏预览和 token 计数。
- Agent message/tool call/approval 只追加，执行状态放独立投影表。
- 检索 trace、citation、评测结果和反馈保存版本引用；长文本/原文使用 MinIO 引用，不写入 MongoDB 日志。
- 报告辅助内容必须由学生确认后进入草稿，不能自动提交。
- 课程关闭、退课、任务终态或账号停用立即禁止新 Agent 调用。
- 教师可查看本课程聚合后的 Agent 使用、引用质量、常见问题和失败类型；查看学生明细必须有课程权限并留审计。

## 二、配额治理

配额按三层取最小可用值：

```text
平台硬上限
  ∩ 课程配额
  ∩ 用户配额
```

维度包括并发实例、并发启动、CPU、内存、磁盘、对象存储、Agent token/请求频率。课程教师可查看本课程配额和用量，但只能申请调整；平台管理员审批/配置。

资源治理还包括课程发布窗口预热、Swarm 服务最小/最大副本、空闲回收和成本预算。预热只创建受控共享缓存或预备容量，不能提前创建未授权学生工作区；扩缩容不能突破 MySQL 配额事实。

启动任务时在 MySQL 原子创建 `QuotaReservation`，成功销毁后释放。Redis 计数只作快速拒绝或监控，不能作为唯一配额事实。定期对账 reservation、task 和外部实例。

## 三、运行时与镜像治理

- 运行时适配器由管理端启停，健康状态不由教师修改。
- 模板只能引用已批准、已扫描的镜像 digest 和资源规格。
- tag 只用于展示，冻结版本锁定 digest。
- 默认网络无出站；白名单按平台策略和课程例外审批。
- 容器/VM 位于隔离网络，浏览器只通过工作区网关访问。
- 外部实例打 opaque 标签，不泄露学生姓名、邮箱和课程敏感内容。
- Swarm 节点按 `edge/app/worker/runtime/data` 标签分池；数据库和日志节点不与实验容器混部，除非经过平台策略批准。
- Swarm Secrets/外部密钥管理器保存数据库、网关、运行时和模型凭据，禁止写入镜像、Git 或普通 Config。
- Manager 至少 3 个并保持 quorum；服务使用健康检查、资源 reservation/limit、滚动更新和失败回滚。
- 运行时 adapter 使用最小权限的 Swarm API 账号；Django Web 不访问 Docker Socket。

## 四、三站点安全

### 会话与 CSRF

- `user`、`teacher`、`admin` 三站 host-only Cookie，不设置父域 Domain。
- Session Cookie：`Secure`、`HttpOnly`、`SameSite=Lax`。
- CSRF Cookie/Token 按站点独立，严格校验 Origin/Referer。
- Session 绑定 portal；网关覆盖可信 `X-Portal`，应用拒绝 mismatch。
- 管理端空闲/绝对超时短于普通用户端；高风险操作要求近期认证。
- 密码变化、账号停用、资格撤销可按站点或全局撤销 Session。

### 浏览器策略

每站独立 CSP，至少：

```text
default-src 'self'
script-src 'self'
object-src 'none'
base-uri 'self'
frame-ancestors 'none'
form-action 'self'
```

工作区 iframe/连接能力按 user-web 的具体功能添加最小来源，不能把宽松策略复制到 teacher/admin。启用 HSTS、`X-Content-Type-Options: nosniff`、合理的 Referrer-Policy 和 Permissions-Policy。

### 管理端加强

- 可叠加 VPN/IP allowlist/WAF，不影响用户端和教师端可用性。
- 教师资格、角色、配额、安全策略、异常销毁必须写原因并二次确认。
- 管理端不得展示可直接复用的工作区凭证、对象存储密钥或完整证件号。
- 管理员不能代替教师审核，后端显式拒绝而非只隐藏按钮。

## 五、上传、对象和导出安全

1. 上传先限制大小、扩展名、magic bytes 和 MIME，再经 ClamAV。
2. 对象进入 MinIO 后登记 `core_object_asset`、digest、大小、所有者和保留期。
3. 浏览器不使用 MinIO 管理接口；上传/下载经过平台授权或短期预签名。
4. 下载 token 一次性或有次数/时间上限，数据库仅存 hash。
5. 课程成果导出记录申请者、批准者、scope、manifest 和下载次数。
6. 只追加事实的对象清理追加 purge log，不回写伪造历史。

## 六、审计

所有管理和不可逆写操作写 AppendOnly AuditLog：

```text
actor_id
actor_portal
actor_qualification/role snapshot
action
course_id（如适用）
target_type / target_id
before_masked / after_masked
result / error_code
client_ip_hash / user_agent summary
trace_id / created_at
```

以下必须审计：登录失败和 portal mismatch、OIDC 绑定/恢复、API Client/Webhook 密钥与状态、教师/管理员资格、课程状态、负责人/助教、选课审批/退出、名册导入、课程复制、内容发布、模板/Rubric/Agent 版本、实验发布/撤回、延期决定、审核决定、导出、配额、安全策略、实例异常销毁、Agent 高风险审批和风险信号人工处置。

审计页面按最小权限显示；教师仅能查看本课程业务审计摘要，不能查询平台安全日志。

## 七、可观测性

### Trace

HTTP 网关生成/透传 trace_id；Django、Outbox、Celery、RuntimeAdapter、MinIO、模型网关和通知沿用。错误响应向用户提供可复制 trace_id，但不暴露内部栈/地址。

### Metrics

| 指标 | 用途 |
|---|---|
| `http_request_duration_seconds{portal,route,status}` | 三站/API 性能与错误率 |
| `portal_login_total{portal,result}` | 门户登录与拒绝 |
| `course_enrollment_decisions_total{mode,result}` | 选课审批和容量冲突 |
| `course_task_assignment_lag_seconds` | 发布/选课到个人任务生成 |
| `course_scope_denied_total{portal,resource}` | 越权尝试趋势 |
| `provisioning_duration_seconds{runtime_type}` | 实例启动耗时 |
| `quota_reserved{dimension}` | 平台/课程/用户资源占用 |
| `sse_event_lag_seconds{portal}` | 事件延迟 |
| `autosave_confirmed_lag_seconds` | 自动保存 RPO |
| `compensation_tasks{status}` | 补偿积压/DEAD |
| `orphan_task/instance/reservation_count` | 对账异常 |
| `agent_tool_calls_total{risk,result}` | Agent 工具与拒绝 |
| `agent_answers_total{mode,citation_status,result}` | Agent 回答、引用和降级质量 |
| `agent_eval_score{suite,dimension}` | Agent 评测门禁趋势；不含用户/课程 ID |
| `course_risk_signals_total{type,result}` | 风险提醒生成、确认和关闭 |
| `resource_cost_amount{resource_type}` | 资源成本和预算趋势 |
| `webhook_deliveries_total{event,result}` | 开放集成投递、重试和死信 |

禁止将 `user_id/course_id` 作为 Prometheus 高基数 label；具体 opaque ID 放 trace/log。

### Logs

结构化日志字段：timestamp、level、service、portal、trace_id、actor opaque id、course/task opaque id、action、result、error_code、duration。禁止写 Session、CSRF、密码、工作区 token、证件原值、完整提示词、签名 URL 和内网凭证。

日志链路固定为：

```text
Nginx/Gateway/Django/Celery/Swarm 节点 stdout
  → Fluent Bit/Vector/OTel Collector（每节点采集、脱敏、批量重试）
  → MongoDB Replica Set（运行日志集合）
```

MongoDB 只保存运行日志和安全/访问日志，不作为 `AuditLog`、任务状态、配额或审核结论的事实源。日志集合必须设置 `created_at` TTL 索引，并按 `service`、`level`、`trace_id`、`course_id`、`resource_id` 建查询索引；高基数用户/课程标识不能直接作为 Prometheus label。采集器不可用时日志暂存本地受限缓冲，不能阻塞业务请求。

## 八、告警

| 等级 | 条件示例 |
|---|---|
| P1 | 孤儿运行实例、配额持续泄露、审计写入失败、归档校验失败且实例待销毁、管理端跨端会话异常 |
| P2 | DEAD 补偿、Outbox 长时间积压、SSE P95 超 2s、选课/任务分配缺口、存储 >85% |
| P3 | 单适配器降级、存储 >70%、课程容量冲突突增、Agent 拒绝率异常 |

告警必须包含 trace/资源引用和处置入口，但不包含敏感字段。P1 不得只发日志而无主动通知。

## 九、数据保留与恢复

- MySQL：每日全量 + binlog，目标 RPO ≤24h、RTO ≤4h。
- 工作区确认数据 RPO ≤30s。
- 报告、成果、归档默认保留 365 天，可由课程策略在平台允许范围内调整。
- 审核结论、任务跃迁、选课事件和审计按合规周期保留，不随课程归档删除。
- MinIO 开启版本控制；清理前校验资产引用和 retention。
- Redis 缓存可重建；Broker/SSE Stream 的可接受丢失窗口必须单独定义，不能把 Redis 当业务事实源。
- MongoDB 日志按保留期做快照/归档，Replica Set 故障时业务请求不得依赖日志写入成功。
- 每月恢复演练，抽样恢复课程、个人任务、报告附件、归档和日志查询，成功率 100%。

## 十、威胁与控制

| 威胁 | 控制 |
|---|---|
| 从用户站复制 Cookie 到管理站 | host-only + Session portal 绑定 + Host/X-Portal 校验 |
| 教师枚举其他课程任务 ID | selector 先裁剪，资源不可见返回 404 |
| 助教越权审核/导出 | deny-by-default grant + service 内重验 + 审计 |
| 并发选课超容量 | 锁课程行 + ACTIVE 计数 + live 唯一约束 |
| 重试重复创建实例/任务 | 幂等记录、唯一索引、adapter idempotency key |
| 前端伪造任务成功 | 状态只来自 MySQL/SSE/API，前端无推进定时器 |
| Agent 提示注入提升工具权限 | 工具执行端固定 policy/scope/审批，与模型文本隔离 |
| RAG 索引返回其他课程片段 | 检索前后双重 ACL + source version scope + 引用访问校验 |
| Agent 无依据编造课程答案 | 强制引用模式 + 无来源降级 + 离线评测和反馈队列 |
| 相似度信号误判学生 | 只作为教师辅助候选，禁止自动拒绝并展示算法版本/证据 |
| 风险模型自动影响学生权益 | 分析只生成可解释投影，不自动退课、扣分或改变任务状态 |
| Webhook 重放或伪造 | HMAC 签名、timestamp、delivery id、scope 和密钥轮换 |
| OIDC 账号错误合并 | issuer+subject 唯一映射、显式绑定确认和安全审计 |
| 退课后继续使用工作区 | 撤销会话 + 网关每次校验 + 终态回收对账 |
| 管理员代替教师审核 | 权限层硬拒绝 + decision 表约束/测试 + 审计 |
