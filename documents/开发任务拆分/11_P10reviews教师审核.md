# P10 reviews 教师审核与自动检查

## 目标

基于 P05/P06 已冻结的 Rubric 实现审核队列、逐项评分、定位批注、自动检查证据、相似度辅助和只追加审核结论，明确禁止平台管理员代审或算法自动定案。

## 后端范围

- 初始 schema：review/decision/auto-check run、criterion score/current projection、criterion score event、annotation revision、similarity run/match；Rubric 定义表已由 P05 建立。
- 按 course staff/grant 裁剪待审报告、过程快照和系统成果；review/task 使用行锁和 If-Match。
- 审核轮次必须沿用 publication 冻结的 `rubric_version`，criterion 当前分值使用 row_version，并为每次修订追加不可变 score event。
- 定位批注绑定报告版本/文件/object digest/位置锚点，审核决定后不可静默覆盖。
- APPROVE/REJECT 决定只追加，结论推动任务状态，拒绝允许按策略生成新报告版本。
- 自动检查引用 P05 冻结规则异步执行，结果与 checker/rule/artifact digest/trace 关联。
- 相似度分析保存算法版本、候选范围和证据，只进入教师辅助队列，禁止自动拒绝、扣分或改变任务状态。
- 审核决定写 Audit/Outbox/通知，准备 P11 归档编排。

## 前端范围

- teacher-web 待审队列、冻结 Rubric 评分、报告/成果/快照只读、定位批注、自动检查、相似度候选、通过/退回和反馈；Rubric 定义管理已在 P05 交付。
- user-web Rubric 结果、定位批注、退回原因和重新提交入口。
- admin-web 仅监管只读，不显示可执行审核决定按钮。

## 测试与验收

- 教师 A 不能读教师 B 课程；无 grant 助教不能读/审/导出。
- 平台管理员调用 decide 永远 403；数据库和 service 双重拒绝。
- 两个审核请求同一 If-Match 一个成功一个 412；重复 key 重放。
- 审核结果不可 update/delete；任务状态和通知最终一致。
- 学生只能看自己的反馈，报告和课程 scope 不泄露。
- Rubric 已发布版本不可覆盖；并发 criterion score/批注编辑遵循 If-Match。
- 相似度运行重放不重复，证据访问按课程裁剪，任何 match 都不能触发自动决定。

## 不做

- 不直接归档/销毁运行实例，不实现成绩单或 OJ；不让 Agent、相似度或自动检查替代教师决定。

## 出口

课程教师可使用冻结 Rubric、批注、自动检查和相似度证据完成真实审核闭环，结论只追加且可追踪，P11 可以根据 APPROVED/终止目标执行归档。
