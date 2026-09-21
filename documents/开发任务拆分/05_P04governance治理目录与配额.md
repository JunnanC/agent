# P04 governance 治理目录、配额与策略

## 目标

建立平台、课程、用户三级配额以及运行时、镜像、资源规格、安全策略、网络白名单、课程预热和扩缩容护栏，为实验启动和成本分析提供可审计的资源事实。

## 后端范围

- 初始 schema：runtime adapter、image asset、resource profile、quota、quota reservation、security policy、network allowlist。
- 管理端维护运行时健康、镜像 digest 扫描/批准、资源规格、平台/课程/用户配额。
- `QuotaReservation` 在 MySQL 原子创建、释放和对账；Redis 只做快速限流/短锁。
- 镜像 tag 只展示，任务引用冻结 digest；资源值、网络策略和风险等级有 service 校验。
- 配置课程实验预热、并发上限、扩缩容冷却、空闲回收和预算阈值；策略只产生运行意图，不直接绕过 provisioning adapter。
- 记录 reservation、实例、存储和预热的计量事实，P13 基于 MySQL 事实生成资源成本投影。
- 观测 Swarm 节点、运行时容量、对象存储和配额使用，生成管理端告警摘要。

## 前端范围

- admin-web：运行时、镜像、资源规格、配额、安全策略、网络白名单、预热/扩缩容和成本护栏页面。
- teacher-web：只读查看本课程配额、预热状态、使用量和预算摘要。
- user-web：仅展示任务可用资源摘要，不提供配置入口。

## 测试与验收

- 平台 ∩ 课程 ∩ 用户配额不能超卖；并发 reservation 一个成功一个冲突。
- 未批准镜像、digest 变更、无效资源值和越权课程 quota 写入均被拒绝。
- Reservation 重试/释放幂等；Redis 清空后 MySQL 事实可重建。
- 管理员高风险策略变更需要 If-Match、近期认证、原因和审计。
- 预热并发不能突破平台/课程配额；扩缩容重放不重复 reservation，冷却和预算护栏可验证。
- 成本计量可由 reservation/instance/object 事实重算，MongoDB 日志不参与结算。
- 运行时 adapter 健康降级能触发告警，不阻塞普通课程读取。

## 不做

- 不在此阶段创建实验实例，不直接调用 Swarm 创建容器。
- 不把 Redis 计数作为配额唯一事实，不开放教师修改平台安全策略。

## 出口

治理数据、扩缩容策略和计量事实可供 P06/P07/P13 使用，管理端可以发现超限、镜像不合规、预算异常和运行时降级。
