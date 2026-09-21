# P05 labtemplates、Rubric、自动检查定义与预检

## 目标

建立课程内模板、不可变版本、课程资料引用、自动检查规则、Rubric 冻结版本、资源规格引用、预检和 digest 冻结，为实验发布提供全部前置定义。

## 后端范围

- `labtemplates_template`、`labtemplates_template_version`、`labtemplates_auto_check_rule`、`labtemplates_template_precheck_run`，以及 `reviews_rubric`、`reviews_rubric_version`、`reviews_rubric_criterion` 初始 schema。
- 课程负责人/授权助教创建模板草稿、生成版本、上传手册和环境资源、启动预检。
- 模板版本可关联 P03 已发布课程资料；跨课程、撤下或无权限资料不得进入冻结上下文。
- 自动检查规则包含 checker 类型、输入/输出 schema、超时、资源上限、网络策略、分值展示策略和失败语义；随模板版本一起冻结。
- 课程负责人/有 `REVIEW_SUBMISSION` grant 的助教创建 Rubric 草稿、criterion 和版本；已发布 Rubric 版本不可覆盖，P06 publication 必须绑定同课程已发布版本。
- 预检使用 P04 已批准镜像/资源 profile；通过后生成 `spec_digest`，发布/引用后字段冻结。
- 已发布版本只能 clone 为新草稿；模板和版本必须与当前 course 同源。
- 为 P03 课程复制 job 注册模板和 Rubric 复制处理器，目标课程生成全新 template/rubric/version public_id 和引用关系，不复用源课程内部主键。
- 上传对象经 core asset、大小/MIME/magic、ClamAV 和 MinIO 受控流程。

## 前端范围

- teacher-web：课程模板列表、草稿编辑、课程资料关联、自动检查规则、版本、预检进度、错误和 clone；Rubric 列表、criterion 编辑、版本与发布。
- admin-web：镜像/预检监管摘要；不替教师修改模板内容。

## 测试与验收

- 跨课程模板、版本、镜像和资源引用返回 404/422。
- DRAFT 版本可更新；PRECHECK/PUBLISHED 版本不可覆盖；clone 产生新版本。
- 预检异步返回 202、阶段事实、trace 和重试语义；重复 key 不重复执行。
- digest 与版本规格不一致、未批准镜像和恶意文件均拒绝。
- 自动检查 schema、超时/资源上限和 sandbox/network policy 纳入预检；规则版本发布后不可覆盖。
- Rubric 已发布版本不可覆盖；跨课程 Rubric 引用拒绝；criterion position、权重/分值和总分约束通过。
- 课程 grant、If-Match、审计和 Outbox 覆盖全部写操作。

## 不做

- 不发布课程实验，不创建个人任务，不启动运行实例。

## 出口

教师可得到课程内唯一、预检通过、自动检查规则与 digest 一并冻结的模板版本，以及已发布 Rubric 版本；P06 可在 publication 中安全绑定，P10 只产生评分与审核事实。
