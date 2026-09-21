# P08 workspaces 工作区、SSE 与自动保存

## 目标

实现 user-web 进入个人实验工作区的短期票据、实时事件、快照、自动保存、命名检查点和受控操作回放；教师只能读取授权过程投影。

## 后端范围

- workspace session、snapshot、autosave log、workspace checkpoint、operation event 初始 schema。
- user-web 任务进入/续签/主动撤销，票据只存 hash/jti，TTL ≤15 分钟，scope 绑定 task/student/instance/capabilities。
- 工作区网关每次校验 portal、票据、任务、选课、实例和撤销状态；teacher/admin 不签发学生票据。
- SSE `/api/v2/events/stream`：portal/object scope 授权、Last-Event-ID、Redis Stream 窗口、MySQL Outbox 回放、心跳和降级。
- 自动保存接收 client_seq，MinIO 存不可变对象，MySQL CAS 更新 latest snapshot，追加 autosave log。
- 检查点绑定 task/workspace version/object digest；恢复产生新版本而不覆盖原快照，并受任务状态、配额和 If-Match 约束。
- 受控工具/命令追加 operation event，回放只返回本人或授权教师可见的脱敏输入、结果摘要、时间和 trace，不保存凭证原值。

## 前端范围

- user-web 全屏实验室、手册/IDE/终端/预览布局、Agent 浮层占位、保存状态、检查点管理和操作回放时间线。
- 共享 event-client 单连接、事件 ID 去重、断线续传、轮询降级和可见连接状态。
- IndexedDB 断网待同步队列、服务端 saved_at、网络恢复 flush 和冲突选择；不注册 Service Worker，不构成 PWA。
- teacher-web 过程快照只读页；admin-web 会话/异常摘要。

## 测试与验收

- 退课、停用、任务终态、销毁后旧票据立即失效。
- 教师不能获取终端/IDE token；跨 task/course 票据返回 401/403。
- SSE 频道越权、重复事件、过期 cursor、断线恢复和 MySQL 回放通过。
- 自动保存旧 seq 不覆盖新快照；重复 seq 幂等；离线恢复不丢待同步内容。
- 检查点创建/恢复重试不产生重复版本，旧 If-Match 返回 412；跨任务检查点拒绝。
- 操作回放按 cursor 稳定分页，学生看不到策略密钥/原始凭证，教师权限撤销后不可继续读取。
- Nginx/Gateway SSE 不 buffering；移动视口操作栏、Agent 浮层和内容不遮挡。

## 不做

- 不实现报告提交、教师审核、终态归档和真实 Swarm 连接。

## 出口

学生可安全进入自己的 Fake 实验工作区并实时接收事件，过程快照和检查点可恢复、操作可审计回放，P09/P12 可引用授权快照与事件摘要。
