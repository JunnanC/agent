# P13 analytics、notifications、integrations 与平台运维

## 目标

完成教学分析、学习建议、风险/质量/成本投影、通知、OIDC、开放 API、签名 Webhook、Prometheus/OTel 指标、MongoDB 日志查询、告警和管理端运维看板。

## 后端与基础设施范围

阶段内按 P13-A（analytics + notifications）、P13-B（integrations）、P13-C（观测/日志/恢复收口）依次验收。每个子批次必须独立完成 schema、API、三端页面、安全测试和出口记录，不能等到 P14 一次性补齐。

- `notifications_notification`、`notifications_preference`，由 Outbox 消费幂等创建。
- 通知按 portal/actor/scope 裁剪；链接使用站点 HTTPS URL + opaque ID，不带 Token。
- analytics 初始 schema：course daily、student risk signal、course quality snapshot、learning recommendation、resource cost daily；全部由 MySQL 业务/计量事实按 source cursor 生成可重建投影。
- 风险信号和学习建议包含 evidence/explanation/model-or-rule version/有效期，只提供人工决策辅助，不自动退课、扣分、选课、延期或改变任务状态。
- integrations 初始 schema：`integrations_oidc_provider`、`integrations_oidc_identity`、`integrations_api_client`、`integrations_api_client_grant`、`integrations_webhook_endpoint`、可变 `integrations_webhook_delivery` 与只追加 `integrations_webhook_delivery_attempt`；secret 只存 hash/密文并支持双密钥轮换。
- OIDC 校验 issuer/state/nonce/PKCE，以 `(issuer, subject)` 唯一绑定；禁止根据 email 静默合并账号。
- 开放 API 只从 P00 建立的 `api.example.edu` 进入，使用 IntegrationPrincipal、client credential/OIDC access token、显式 scope、课程 grant 和独立限流；不模拟浏览器 portal 或绕过对象权限。
- Webhook 对 delivery id/timestamp/body digest 做 HMAC 签名；delivery 管理调度状态，每次网络请求追加 attempt，指数退避、重试、死信和重放保护均有持久事实。
- HTTP、Celery、Outbox、SSE、Swarm adapter、MinIO、Agent、选课和任务指标；禁止高基数 ID 作为 Prometheus label。
- Nginx/Gateway/Django/Celery/Swarm 节点 JSON stdout 经 Fluent Bit/Vector/OTel Collector 脱敏写 MongoDB `runtime_logs`。
- MongoDB TTL、Replica Set 健康、查询索引、日志容量、P1/P2/P3 告警和 admin-web 看板。
- 备份任务、恢复演练记录、孤儿 task/instance/reservation、DEAD Outbox/补偿处理入口。

## 前端范围

- 三端通知中心、已读/偏好和跨站链接。
- user-web：个人解释性学习建议、风险提示和个人任务/反馈通知；不出现自动执行按钮。
- teacher-web：课程参与/进度/风险/质量/Agent/资源成本分析，以及课程任务/审核通知。
- admin-web：平台质量/成本/投影新鲜度、OIDC provider、API Client/scope、Webhook/投递死信；运维总览包含错误率、队列、Outbox、补偿、配额、实例、存储、日志和安全拒绝。

## 测试与验收

- 同一 Outbox 事件不重复创建通知；用户不能读/改他人通知。
- 投影 job 重放不重复累计，删除投影后可从 MySQL source cursor 重建；MongoDB 不作为分析事实源。
- 风险信号、相似度和学习建议不能自动影响学生权益或业务状态，教师处置使用 If-Match 并留审计。
- OIDC issuer+subject 并发绑定只能一个成功；错误 redirect/state/nonce/issuer 稳定拒绝。
- API client 越权 scope/课程访问拒绝；密钥轮换后旧密钥仅在受控过渡窗有效且明文不回显。
- Webhook 签名、重放拒绝、退避、重复事件幂等、死信和人工重试通过。
- trace 可从 API 错误查到 Worker、MongoDB 日志和 AuditLog。
- MongoDB 暂时不可用不阻塞业务；日志脱敏和 TTL 生效，日志故障触发告警。
- 告警不包含密码、Cookie、票据、签名 URL 和证件原值；P1 有主动通知。
- 管理端只能按授权查看课程审计摘要，平台安全日志不下放教师。

## 不做

- 不在此阶段改变业务状态机或新增领域权限。
- 不建设 Moodle/Canvas/LTI、成绩回传或其他 LMS 专用连接器。
- 不交付 PWA、离线通知、独立移动端只读模式、国际化或专项无障碍模块。

## 出口

平台具备可重建教学/质量/成本投影、可靠通知和受控开放集成；核心业务与基础设施可观测，日志可检索且不承载业务事实。
