from apps.core.http import error_response
from apps.workspaces.adapters import fake_workspace_token_adapter


class WorkspaceServiceError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def issue_workspace_session(
    *,
    request,
    task_public_id: str,
    student_public_id: str,
    instance_public_id: str,
    idempotency_key: str,
) -> dict:
    if not idempotency_key or idempotency_key.strip() != idempotency_key:
        raise WorkspaceServiceError(
            status_code=400,
            code="IDEMPOTENCY_KEY_INVALID",
            message="Idempotency-Key 必须为非空且不含首尾空格的字符串",
            details={"header": "Idempotency-Key"},
        )
    if len(idempotency_key.encode("utf-8")) > 255:
        raise WorkspaceServiceError(
            status_code=400,
            code="IDEMPOTENCY_KEY_INVALID",
            message="Idempotency-Key 长度不能超过 255 字节",
            details={"header": "Idempotency-Key", "max_bytes": 255},
        )
    if not fake_workspace_token_adapter.validate_context(
        task_public_id=task_public_id,
        student_public_id=student_public_id,
        instance_public_id=instance_public_id,
    ):
        raise WorkspaceServiceError(
            status_code=409,
            code="WORKSPACE_CONTEXT_INVALID",
            message="工作区上下文不可用或状态不允许签发",
            details={},
        )

    return fake_workspace_token_adapter.issue(
        task_public_id=task_public_id,
        student_public_id=student_public_id,
        instance_public_id=instance_public_id,
        idempotency_key=idempotency_key,
    )


def renew_workspace_session(
    *,
    session_public_id: str,
    task_public_id: str,
    student_public_id: str,
    instance_public_id: str,
) -> dict:
    if not fake_workspace_token_adapter.validate_context(
        task_public_id=task_public_id,
        student_public_id=student_public_id,
        instance_public_id=instance_public_id,
    ):
        raise WorkspaceServiceError(
            status_code=409,
            code="WORKSPACE_CONTEXT_INVALID",
            message="选课、任务或实例状态不允许续签",
            details={},
        )
    try:
        return fake_workspace_token_adapter.renew(
            session_public_id=session_public_id,
            task_public_id=task_public_id,
            student_public_id=student_public_id,
            instance_public_id=instance_public_id,
        )
    except KeyError:
        raise WorkspaceServiceError(
            status_code=409,
            code="WORKSPACE_SESSION_INVALID",
            message="工作区会话不存在、已撤销或上下文不匹配",
            details={},
        )


def revoke_workspace_session(
    *,
    session_public_id: str,
    student_public_id: str,
) -> dict:
    try:
        return fake_workspace_token_adapter.revoke(
            session_public_id=session_public_id,
            student_public_id=student_public_id,
        )
    except KeyError:
        raise WorkspaceServiceError(
            status_code=404,
            code="WORKSPACE_SESSION_NOT_FOUND",
            message="工作区会话不存在或非本人会话",
            details={},
        )


def save_workspace_snapshot(
    *,
    request,
    task_public_id: str,
    client_seq: int,
    payload: dict,
) -> dict:
    try:
        return fake_workspace_token_adapter.snapshot(
            task_public_id=task_public_id,
            client_seq=client_seq,
            payload=payload,
        )
    except ValueError:
        raise WorkspaceServiceError(
            status_code=409,
            code="CLIENT_SEQ_CONFLICT",
            message="client_seq 小于服务端最新快照序号",
            details={"client_seq": client_seq},
        )


def verify_workspace_token(
    *,
    token_hash: str,
    task_public_id: str,
    student_public_id: str,
    instance_public_id: str,
) -> dict:
    return fake_workspace_token_adapter.verify(
        token_hash=token_hash,
        task_public_id=task_public_id,
        student_public_id=student_public_id,
        instance_public_id=instance_public_id,
    )


def workspace_service_error_response(request, error: WorkspaceServiceError):
    return error_response(
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        details=error.details,
        request=request,
    )
