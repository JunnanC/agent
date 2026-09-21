# P02 accounts 与三门户身份

## 目标

建立账号、身份资料、教师资格、平台管理员资格和 portal 绑定 Session；让三个站点能独立登录、退出和吊销会话。

## 后端范围

- 初始 schema：`accounts_user`、`accounts_identity_verification`、`accounts_teacher_qualification` 及事件、`accounts_platform_admin_assignment` 及事件。
- 登录、登出、全量登出、改密、`GET /api/v2/me`、资料更新、身份资料提交/审核。
- `PortalContextMiddleware` 只接受 Nginx/Gateway 注入的可信 `X-Portal`；USER/TEACHING/PLATFORM 准入分别检查。
- Session/CSRF 使用 host-only Cookie、`Secure`、`HttpOnly`、`SameSite=Lax`；Portal mismatch、停用、资格撤销和改密吊销会话。
- 不设置全局角色列；教师资格和平台管理员资格分别由资格表表达。

## 前端范围

- 三端各自 `/login`、登录失败、会话过期、无门户准入和登出页面。
- 共享 `auth-client`：CSRF 初始化、`/me`、SessionProvider、portal mismatch 处理。
- user-web 个人资料；admin-web 用户、教师资格、管理员资格和身份审核；teacher-web 只消费门户准入摘要。

## 测试与验收

- USER Session 复制到 TEACHING/PLATFORM 被拒绝；伪造 `X-Portal` 不改变后端判定。
- 教师资格撤销、平台管理员撤销、账号停用、改密后旧 Session 立即失效。
- 登录错误不泄露账号是否存在；按 IP+账号限流。
- 身份证件只存 hash/masked/reference；响应、日志、审计均无原值。
- 三端分别登录/退出/过期，浏览器 localStorage 不保存 Session 或 Token。

## 不做

- 不实现 `teams`、课程、选课、JWT、全局业务角色或学生实验权限。
- 不实现父域 Cookie SSO；统一登录在 P13 通过独立 OIDC provider/identity 能力实现。

## 出口

空数据库可创建测试账号，三个站点可以独立登录并由服务端返回可信门户和资格摘要；后续课程权限可安全引用 User 和资格事实。
