from typing import Protocol


class WorkspaceTokenPort(Protocol):
    def validate_context(
        self,
        *,
        task_public_id: str,
        student_public_id: str,
        instance_public_id: str,
    ) -> bool:
        """Revalidate enrollment, task, and runtime instance state."""

    def issue(
        self,
        *,
        task_public_id: str,
        student_public_id: str,
        instance_public_id: str,
        idempotency_key: str,
    ) -> dict:
        """Issue a workspace token once for an idempotency key."""

    def renew(
        self,
        *,
        session_public_id: str,
        task_public_id: str,
        student_public_id: str,
        instance_public_id: str,
    ) -> dict:
        """Renew a token after revalidating the workspace context."""

    def revoke(
        self,
        *,
        session_public_id: str,
        student_public_id: str,
    ) -> dict:
        """Revoke the session and append an audit fact."""

    def verify(
        self,
        *,
        token_hash: str,
        task_public_id: str,
        student_public_id: str,
        instance_public_id: str,
    ) -> dict:
        """Read the latest token, scope, and revocation facts."""

    def snapshot(
        self,
        *,
        task_public_id: str,
        client_seq: int,
        payload: dict,
    ) -> dict:
        """Apply monotonic and idempotent snapshot sequencing."""
