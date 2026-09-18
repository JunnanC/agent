from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.http import Http404, HttpRequest, JsonResponse
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import exception_handler

from .context import current_request_id
from .responses import failure


@dataclass(frozen=True)
class ErrorCode:
    code: int
    symbol: str
    http_status: int
    message: str


VALIDATION_ERROR = ErrorCode(40001, "VALIDATION_ERROR", 400, "请求参数无效")
INVALID_ROLE = ErrorCode(40003, "INVALID_ROLE", 400, "角色必须是内置角色")
EMPTY_FILTER = ErrorCode(40004, "EMPTY_FILTER", 400, "筛选条件不能为空")
UNAUTHENTICATED = ErrorCode(40101, "UNAUTHENTICATED", 401, "未登录")
TOKEN_EXPIRED = ErrorCode(40102, "TOKEN_EXPIRED", 401, "登录已过期")
REFRESH_TOKEN_REVOKED = ErrorCode(40103, "REFRESH_TOKEN_REVOKED", 401, "刷新令牌已失效")
FORBIDDEN = ErrorCode(40301, "FORBIDDEN", 403, "没有访问权限")
ACCOUNT_DISABLED = ErrorCode(40302, "ACCOUNT_DISABLED", 403, "账号已禁用")
MEMBERSHIP_REQUIRED = ErrorCode(40303, "MEMBERSHIP_REQUIRED", 403, "需要成员身份")
MEMBERSHIP_PENDING = ErrorCode(40304, "MEMBERSHIP_PENDING", 403, "成员身份待审核")
MEMBERSHIP_INACTIVE = ErrorCode(40305, "MEMBERSHIP_INACTIVE", 403, "成员身份未激活")
RESOURCE_NOT_FOUND = ErrorCode(40401, "RESOURCE_NOT_FOUND", 404, "资源不存在")
STATE_CONFLICT = ErrorCode(40901, "STATE_CONFLICT", 409, "状态冲突")
IDEMPOTENCY_CONFLICT = ErrorCode(40902, "IDEMPOTENCY_CONFLICT", 409, "幂等请求冲突")
REVISION_CONFLICT = ErrorCode(40903, "REVISION_CONFLICT", 409, "版本冲突")
MEMBERSHIP_CHANGE_BLOCKED = ErrorCode(40904, "MEMBERSHIP_CHANGE_BLOCKED", 409, "成员变更被阻止")
LAST_TEAM_ADMIN_PROTECTED = ErrorCode(40905, "LAST_TEAM_ADMIN_PROTECTED", 409, "最后管理员不可移除")
FILE_TOO_LARGE = ErrorCode(41301, "FILE_TOO_LARGE", 413, "文件过大")
POLICY_REJECTED = ErrorCode(42201, "POLICY_REJECTED", 422, "策略拒绝")
QUOTA_EXCEEDED = ErrorCode(42202, "QUOTA_EXCEEDED", 422, "配额不足")
PRECHECK_FAILED = ErrorCode(42203, "PRECHECK_FAILED", 422, "前置检查失败")
FILE_SCAN_FAILED = ErrorCode(42204, "FILE_SCAN_FAILED", 422, "文件扫描失败")
AUDIT_EXPORT_TOO_LARGE = ErrorCode(42205, "AUDIT_EXPORT_TOO_LARGE", 422, "审计导出记录过多")
RATE_LIMITED = ErrorCode(42901, "RATE_LIMITED", 429, "请求过于频繁")
FILE_UPLOAD_LIMITED = ErrorCode(42902, "FILE_UPLOAD_LIMITED", 429, "上传过于频繁")
INTERNAL_ERROR = ErrorCode(50001, "INTERNAL_ERROR", 500, "服务器内部错误")
RUNTIME_UNAVAILABLE = ErrorCode(50301, "RUNTIME_UNAVAILABLE", 503, "运行时不可用")
DEPENDENCY_UNAVAILABLE = ErrorCode(50302, "DEPENDENCY_UNAVAILABLE", 503, "依赖服务不可用")
AGENT_TOOL_REJECTED = ErrorCode(42211, "AGENT_TOOL_REJECTED", 422, "工具调用被拒绝")
WORKSPACE_ACCESS_DENIED = ErrorCode(42212, "WORKSPACE_ACCESS_DENIED", 403, "工作区访问被拒绝")
TEMPLATE_VERSION_NOT_PUBLISHED = ErrorCode(
    42213, "TEMPLATE_VERSION_NOT_PUBLISHED", 422, "模板版本未发布"
)
REVIEW_ALREADY_EXISTS = ErrorCode(42214, "REVIEW_ALREADY_EXISTS", 409, "审核记录已存在")
REPORT_ALREADY_SUBMITTED = ErrorCode(42215, "REPORT_ALREADY_SUBMITTED", 409, "报告已提交")
ARCHIVE_NOT_COMPLETED = ErrorCode(42216, "ARCHIVE_NOT_COMPLETED", 409, "归档未完成")
ASSIGNMENT_NOT_ACTIVE = ErrorCode(42217, "ASSIGNMENT_NOT_ACTIVE", 409, "任务未激活")
TIME_WINDOW_INVALID = ErrorCode(42218, "TIME_WINDOW_INVALID", 422, "时间窗口无效")
TEMPLATE_NOT_PUBLISHED = ErrorCode(42219, "TEMPLATE_NOT_PUBLISHED", 422, "模板未发布")
USER_NOT_ACTIVE_MEMBER = ErrorCode(42220, "USER_NOT_ACTIVE_MEMBER", 403, "用户不是有效成员")
CANNOT_WITHDRAW_STATUS = ErrorCode(42221, "CANNOT_WITHDRAW_STATUS", 409, "当前状态不可撤回")

ERROR_CODES = {
    error.symbol: error
    for error in (
        VALIDATION_ERROR,
        INVALID_ROLE,
        EMPTY_FILTER,
        UNAUTHENTICATED,
        TOKEN_EXPIRED,
        REFRESH_TOKEN_REVOKED,
        FORBIDDEN,
        ACCOUNT_DISABLED,
        MEMBERSHIP_REQUIRED,
        MEMBERSHIP_PENDING,
        MEMBERSHIP_INACTIVE,
        RESOURCE_NOT_FOUND,
        STATE_CONFLICT,
        IDEMPOTENCY_CONFLICT,
        REVISION_CONFLICT,
        MEMBERSHIP_CHANGE_BLOCKED,
        LAST_TEAM_ADMIN_PROTECTED,
        FILE_TOO_LARGE,
        POLICY_REJECTED,
        QUOTA_EXCEEDED,
        PRECHECK_FAILED,
        FILE_SCAN_FAILED,
        AUDIT_EXPORT_TOO_LARGE,
        RATE_LIMITED,
        FILE_UPLOAD_LIMITED,
        INTERNAL_ERROR,
        RUNTIME_UNAVAILABLE,
        DEPENDENCY_UNAVAILABLE,
        AGENT_TOOL_REJECTED,
        WORKSPACE_ACCESS_DENIED,
        TEMPLATE_VERSION_NOT_PUBLISHED,
        REVIEW_ALREADY_EXISTS,
        REPORT_ALREADY_SUBMITTED,
        ARCHIVE_NOT_COMPLETED,
        ASSIGNMENT_NOT_ACTIVE,
        TIME_WINDOW_INVALID,
        TEMPLATE_NOT_PUBLISHED,
        USER_NOT_ACTIVE_MEMBER,
        CANNOT_WITHDRAW_STATUS,
    )
}
ERRORS_BY_CODE = {error.code: error for error in ERROR_CODES.values()}


class ApiError(Exception):
    def __init__(
        self,
        error: ErrorCode,
        *,
        message: str | None = None,
        details: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message or error.message)
        self.error = error
        self.error_message = message or error.message
        self.details = details or []


def error_response(
    error: ErrorCode,
    request_id: str | None = None,
    *,
    details: list[dict[str, str]] | None = None,
    message: str | None = None,
) -> JsonResponse:
    return JsonResponse(
        failure(
            error.code,
            message or error.message,
            request_id or current_request_id(),
            details,
        ),
        status=error.http_status,
    )


def _details_from_response_data(data: Any) -> list[dict[str, str]]:
    if isinstance(data, dict):
        return [{"field": str(key), "issue": str(value)} for key, value in data.items()]
    if isinstance(data, list):
        return [{"field": "non_field_errors", "issue": str(value)} for value in data]
    if data:
        return [{"field": "non_field_errors", "issue": str(data)}]
    return []


def drf_exception_handler(exc: Exception, context: dict[str, Any]) -> JsonResponse:
    request = context.get("request")
    request_id = current_request_id()
    if isinstance(request, HttpRequest):
        request_id = request.headers.get("X-Request-ID", request_id)

    if isinstance(exc, ApiError):
        return error_response(
            exc.error,
            request_id,
            details=exc.details,
            message=exc.error_message,
        )
    if isinstance(exc, Http404):
        return error_response(RESOURCE_NOT_FOUND, request_id)
    if isinstance(exc, PermissionDenied):
        return error_response(FORBIDDEN, request_id)

    response = exception_handler(exc, context)
    if response is None:
        return error_response(INTERNAL_ERROR, request_id)

    error_by_status = {
        400: VALIDATION_ERROR,
        401: UNAUTHENTICATED,
        403: FORBIDDEN,
        404: RESOURCE_NOT_FOUND,
        409: STATE_CONFLICT,
        413: FILE_TOO_LARGE,
        422: POLICY_REJECTED,
        429: RATE_LIMITED,
        500: INTERNAL_ERROR,
        503: DEPENDENCY_UNAVAILABLE,
    }
    error = error_by_status.get(response.status_code, INTERNAL_ERROR)
    return error_response(
        error,
        request_id,
        details=_details_from_response_data(response.data),
    )
