# P06 experiments 发布、先修、延期、受众与个人任务

## 目标

实现课程实验发布、先修判定、受众快照、个人任务生成、延期/补交和 14 态任务状态机，使学生获得正确归属和个人有效时间窗的独立任务。

## 后端范围

- 初始 schema：publication（含 rubric_version FK）、audience、experiment task、state transition、task extension request/decision。
- 课程教师使用冻结模板版本和 P05 已发布 Rubric 创建发布草稿，设置 ALL_ACTIVE/SELECTED、晚选策略、窗口、报告策略及 `MANUAL/MANUAL_WITH_AUTO_CHECK`；所有最终决定仍由教师作出。
- 发布/补建按课程与章节先修状态计算 eligible/blockers；先修未满足不能由前端参数绕过。
- 发布事务锁定 course/version/publication，冻结受众规则，批量或分片幂等创建个人任务。
- task 必须绑定 publication、course、enrollment、student、template_version；唯一 `(publication, student)`。
- 集中任务状态机、允许动作、失败记录、终止目标和状态事件；课程关闭不等于任务终止。
- 学生提交延期/补交申请，授权教师追加批准/拒绝决定；批准只生成个人 effective window，不覆盖 publication 原窗口。
- `transaction.on_commit` 触发任务分配补偿和通知。

## 前端范围

- teacher-web：实验草稿、先修、受众、发布时间窗、发布进度、延期决定、任务追踪和课程汇总。
- user-web：我的实验列表、先修阻断、任务详情、个人有效时间窗、延期/补交申请、冻结环境信息、允许动作和装载入口。
- admin-web：跨课程只读异常任务摘要。

## 测试与验收

- 发布重试、Worker 重放和晚选补建不重复创建 task。
- SELECTED enrollment 必须 ACTIVE 且同课程；跨课程引用被拒绝。
- publication 的 template_version 和 rubric_version 必须均已发布且与课程同源，缺失或跨课程引用不能发布。
- 任务状态非法跃迁稳定报错；终态不可重启；失败阶段和 retryable 信息完整。
- 同一延期申请的两个并发决定只有一个成功；决定历史不可覆盖，其他学生和 publication 窗口不受影响。
- 推荐或风险信号不能自动申请延期、改变受众或推进任务状态。
- 并发 start 尚未实现时仍验证状态机锁和唯一边界；教师/学生/管理员 scope 全覆盖。
- 发布和任务事件、审计、指标、OpenAPI 202 语义通过。

## 不做

- 不创建 Swarm/VM 实例，不签发工作区 token，不实现报告审核。

## 出口

教师可发布带先修条件的课程实验并处理个人延期，学生可看到只属于本人的任务和有效时间窗；发布、补建、决定、状态跃迁和对账具备幂等事实。
