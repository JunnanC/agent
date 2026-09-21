# P07 provisioning 装载作业与 FakeRuntime

## 目标

把任务启动变成异步、可重试、可补偿的装载流程，先以 FakeRuntime 完成完整编排，不依赖 Docker/VM。

## 后端范围

- `provisioning_instance`、`provisioning_job`、`provisioning_stage_event`、failure/compensation 关联。
- `RuntimeAdapter` Protocol 与 FakeRuntime：preflight/create/status/endpoint/snapshot/destroy。
- 启动事务锁 task、课程/用户/平台 quota，原子预留、任务转 PROVISIONING、创建 job/outbox，返回 202。
- 六阶段创建：QUOTA_CHECK、IMAGE_PREPARE、CREATE、NETWORK_ATTACH、BOOT_PROBE、WORKSPACE_READY。
- 失败阶段、重试、超时、孤儿实例和配额释放补偿；Web 不调用 adapter。

## 前端范围

- user-web 任务装载页：阶段、状态、取消/重试、错误码、脱敏原因和可复制 trace。
- teacher-web 只读过程追踪；admin-web 运行作业、失败和补偿摘要。

## 测试与验收

- 同一 task 并发 start 只产生一个 job/reservation。
- FakeRuntime 每个阶段可注入超时、失败、部分成功；补偿清理可验证。
- `202 + Location + events_channel` 正确；SSE 不在线时状态仍可轮询。
- 任务状态、实例、reservation、stage event、Audit/Outbox 账目一致。
- 运行时适配器凭证不出 Web 日志，Django Web 无 Docker Socket。

## 不做

- 不连接真实 Swarm/VM，不开放终端或工作区票据。

## 出口

无真实运行时也能完成启动、失败、重试、补偿和对账主链路，P08 可接入工作区网关。
