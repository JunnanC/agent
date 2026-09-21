# P09 reports 报告、附件与成果

## 目标

实现报告草稿、附件、冻结版本和系统成果，使学生能提交可审计、不可覆盖的成果版本。

## 后端范围

- `reports_report_draft`、`reports_report_attachment`、`reports_report_version`、`reports_report_version_attachment`、`reports_system_artifact`。
- 草稿按 task/student scope 读写，If-Match/CAS 防止覆盖；附件走 core asset、ClamAV、MinIO 和下载授权。
- 提交事务锁 task/draft，校验快照 digest 和任务状态，创建 AppendOnly report version，任务转 UNDER_REVIEW，写 Audit/Outbox。
- 报告版本、附件映射和系统成果只追加；下载通过一次性 grant、过期/次数/课程 scope 检查。

## 前端范围

- user-web 报告编辑、草稿保存、附件扫描状态、提交确认、提交历史和 trace。
- teacher-web 报告/成果只读预览入口；admin-web 资产/扫描异常摘要。

## 测试与验收

- 同一提交幂等；草稿 If-Match 冲突返回 412，不覆盖他人修改。
- 扫描未通过或未完成时不可提交/展示给教师；对象 key 不使用用户原文件名。
- 任务、enrollment、course、快照和报告必须同源；跨任务下载返回 404。
- 冻结版本不可更新；下载 token 过期、超次、撤销均失败。
- 报告版本、附件、审计和 Outbox 在一个事务内形成正确事实。

## 不做

- 不作教师审核决定，不执行归档销毁，不开放管理员代提交。

## 出口

学生可形成可审计的报告版本和成果资产，P10 可读取待审内容，P11 可读取冻结版本。
