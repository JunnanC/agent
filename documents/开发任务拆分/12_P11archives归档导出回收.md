# P11 archives 归档、导出与资源回收

## 目标

实现报告/过程归档校验、受控导出、工作区撤销、实例销毁和配额释放，形成终态闭环。

## 后端范围

- `archives_archive_job`、`archives_archive_manifest`、`archives_archive_verification`、`archives_export_grant`。
- 审核通过、课程关闭、到期或取消触发 ARCHIVING → DESTROYING；已启动任务不得直接写终态。
- 生成归档 manifest、对象 digest 和校验记录；校验失败阻止标记归档成功和正常进入目标终态，并进入补偿/管理告警，但不能让运行实例超过安全回收期限继续存活。
- 到达安全回收期限仍未完成归档时，撤销工作区、销毁实例并释放 quota；任务保留 `terminal_target` 并进入 `FAILED`，归档补偿成功后再由统一状态服务收口。
- 撤销 workspace session、销毁运行时、验证外部不存在、释放 quota、推进 COMPLETED/CANCELLED/EXPIRED。
- 导出按 course scope、批准人、短期 token、次数和 retention 控制；状态事实只追加。

## 前端范围

- teacher-web 归档状态、校验、课程成果导出申请和下载进度。
- user-web 个人归档/反馈只读结果；admin-web 异常回收、孤儿实例和 DEAD 补偿处理。

## 测试与验收

- 归档清单 digest/对象缺失/扫描失败会阻止正常完成；测试同时验证安全回收期限到达后实例仍被销毁、quota 被释放，且任务保持可补偿而不伪装成终态。
- 归档成功后票据失效、实例不存在、reservation RELEASED，终态不可重启。
- 外部销毁成功但 DB 回写失败可被对账/补偿发现；重复销毁幂等。
- 平台管理员异常销毁需要原因、近期认证、幂等和审计，不能改审核结论。
- 导出 scope 越权、过期、超次、撤销和审计全部覆盖。

## 不做

- 不实现真实 Swarm adapter（P14 完成）；本阶段用 FakeRuntime 验收状态编排。

## 出口

任务可从审核/到期进入安全终态，所有对象、会话、实例和配额均有可验证收口事实。
