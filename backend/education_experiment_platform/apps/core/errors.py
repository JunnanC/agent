"""统一错误码目录（doc 02 §八、doc 08 §1.5）。

错误码是**字符串常量**而不是自增整数：客户端按 ``symbol`` 分支，文档规定
「统一封装，稳定 code」，因此 code 一旦发布就不能改名，只能新增。

约定：
* 数值前缀不作为 code 使用，HTTP 状态由 ``http_status`` 单独表达；
  同一个 HTTP 状态可以对应多个业务 code（例如 409 下的容量满与状态冲突）。
* 业务代码**禁止内联字符串**，一律引用本模块常量，否则文档与实现会静默漂移。
* 本表只登记文档已定义的 symbol；新增 code 必须先改文档再改这里。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ErrorCode:
    """一个稳定的错误码定义。"""

    code: str
    http_status: int
    message: str
    retryable: bool = False


# ── 400 请求本身不合法 ────────────────────────────────────────
VALIDATION_ERROR = ErrorCode("VALIDATION_ERROR", 400, "请求参数无效")
PORTAL_UNKNOWN = ErrorCode("PORTAL_UNKNOWN", 400, "门户上下文无效")
PROXY_CONTEXT_UNTRUSTED = ErrorCode("PROXY_CONTEXT_UNTRUSTED", 400, "请求入口不受信任")

# ── 401 未认证或会话不可继续 ──────────────────────────────────
AUTH_REQUIRED = ErrorCode("AUTH_REQUIRED", 401, "未登录")
SESSION_PORTAL_MISMATCH = ErrorCode("SESSION_PORTAL_MISMATCH", 401, "会话与门户不一致")
SESSION_REAUTH_REQUIRED = ErrorCode("SESSION_REAUTH_REQUIRED", 401, "需要重新认证")

# ── 403 已认证但无权 ─────────────────────────────────────────
PORTAL_ACCESS_DENIED = ErrorCode("PORTAL_ACCESS_DENIED", 403, "当前门户无权访问该资源")
TEACHER_QUALIFICATION_REQUIRED = ErrorCode(
    "TEACHER_QUALIFICATION_REQUIRED", 403, "需要有效教师资格"
)
PLATFORM_ACCESS_REQUIRED = ErrorCode("PLATFORM_ACCESS_REQUIRED", 403, "需要管理员资格")
COURSE_GRANT_REQUIRED = ErrorCode("COURSE_GRANT_REQUIRED", 403, "没有该课程的授权")
ENROLLMENT_NOT_ACTIVE = ErrorCode("ENROLLMENT_NOT_ACTIVE", 403, "选课未生效")

# ── 404 不存在或不可见（不泄露对象存在性，doc 08 §1.5）─────────
RESOURCE_NOT_FOUND = ErrorCode("RESOURCE_NOT_FOUND", 404, "资源不存在")

# ── 409 当前状态不允许该操作 ─────────────────────────────────
COURSE_STATE_CONFLICT = ErrorCode("COURSE_STATE_CONFLICT", 409, "课程状态不允许该操作")
ENROLLMENT_CAPACITY_FULL = ErrorCode("ENROLLMENT_CAPACITY_FULL", 409, "课程名额已满")
ENROLLMENT_BLOCKED = ErrorCode("ENROLLMENT_BLOCKED", 409, "选课状态变更被阻止")
ENROLLMENT_ALREADY_LIVE = ErrorCode("ENROLLMENT_ALREADY_LIVE", 409, "已存在有效选课")
STAFF_ALREADY_ACTIVE = ErrorCode("STAFF_ALREADY_ACTIVE", 409, "该教师已在教学团队中")
OWNER_TRANSFER_BLOCKED = ErrorCode("OWNER_TRANSFER_BLOCKED", 409, "负责人交接被阻止")
LAST_OWNER_PROTECTED = ErrorCode("LAST_OWNER_PROTECTED", 409, "不可移除课程唯一负责人")
QUOTA_EXCEEDED = ErrorCode("QUOTA_EXCEEDED", 409, "配额不足")

# ── 412 并发前置条件失败 ─────────────────────────────────────
ROW_VERSION_CONFLICT = ErrorCode("ROW_VERSION_CONFLICT", 412, "资源已被他人修改")

# ── 422 语义上不可接受 ───────────────────────────────────────
IDEMPOTENCY_KEY_REUSED = ErrorCode("IDEMPOTENCY_KEY_REUSED", 422, "幂等键已用于不同请求体")
# doc 02 §八 只给了代码示例，未定义「同键请求仍在进行中」的情形。
# 这里显式补一个 code，而不是复用 IDEMPOTENCY_KEY_REUSED：
# 后者语义是「客户端改写了请求体」，让合法重试收到该错误会误导客户端放弃重试。
IDEMPOTENCY_IN_PROGRESS = ErrorCode(
    "IDEMPOTENCY_IN_PROGRESS", 409, "同一幂等键的请求正在处理中", retryable=True
)
IMMUTABLE_VERSION = ErrorCode("IMMUTABLE_VERSION", 422, "已冻结的内容不可修改")
CROSS_COURSE_REFERENCE = ErrorCode("CROSS_COURSE_REFERENCE", 422, "不允许跨课程引用")

# ── 428 缺少 If-Match ────────────────────────────────────────
PRECONDITION_REQUIRED = ErrorCode("PRECONDITION_REQUIRED", 428, "缺少 If-Match 前置条件")

# ── 429 / 5xx ───────────────────────────────────────────────
RATE_LIMITED = ErrorCode("RATE_LIMITED", 429, "请求过于频繁", retryable=True)
INTERNAL_ERROR = ErrorCode("INTERNAL_ERROR", 500, "服务器内部错误")
RUNTIME_UNAVAILABLE = ErrorCode("RUNTIME_UNAVAILABLE", 503, "运行时不可用", retryable=True)
ADAPTER_DEGRADED = ErrorCode("ADAPTER_DEGRADED", 503, "适配器降级", retryable=True)

# 显式列成元组而不是扫描模块全局量：这样「定义了却忘记登记」会在评审时暴露，
# 而不是被静默地自动纳入注册表。
_REGISTERED: tuple[ErrorCode, ...] = (
    VALIDATION_ERROR,
    PORTAL_UNKNOWN,
    PROXY_CONTEXT_UNTRUSTED,
    AUTH_REQUIRED,
    SESSION_PORTAL_MISMATCH,
    SESSION_REAUTH_REQUIRED,
    PORTAL_ACCESS_DENIED,
    TEACHER_QUALIFICATION_REQUIRED,
    PLATFORM_ACCESS_REQUIRED,
    COURSE_GRANT_REQUIRED,
    ENROLLMENT_NOT_ACTIVE,
    RESOURCE_NOT_FOUND,
    COURSE_STATE_CONFLICT,
    ENROLLMENT_CAPACITY_FULL,
    ENROLLMENT_BLOCKED,
    ENROLLMENT_ALREADY_LIVE,
    STAFF_ALREADY_ACTIVE,
    OWNER_TRANSFER_BLOCKED,
    LAST_OWNER_PROTECTED,
    QUOTA_EXCEEDED,
    ROW_VERSION_CONFLICT,
    IDEMPOTENCY_KEY_REUSED,
    IDEMPOTENCY_IN_PROGRESS,
    IMMUTABLE_VERSION,
    CROSS_COURSE_REFERENCE,
    PRECONDITION_REQUIRED,
    RATE_LIMITED,
    INTERNAL_ERROR,
    RUNTIME_UNAVAILABLE,
    ADAPTER_DEGRADED,
)

ERROR_CODES: dict[str, ErrorCode] = {item.code: item for item in _REGISTERED}


class ApiError(Exception):
    """业务错误。视图层统一由异常处理器转成错误信封，不在视图里拼 JSON。"""

    def __init__(
        self,
        error: ErrorCode,
        *,
        message: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or error.message)
        self.error = error
        self.message = message or error.message
        self.detail = detail or {}
