import hashlib
import secrets
import threading
import uuid


class FakeWorkspaceTokenAdapter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, dict] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._snapshots: dict[str, int] = {}
        self._audit: list[dict] = []

    def validate_context(
        self,
        *,
        task_public_id: str,
        student_public_id: str,
        instance_public_id: str,
    ) -> bool:
        return all((task_public_id, student_public_id, instance_public_id))

    def issue(
        self,
        *,
        task_public_id: str,
        student_public_id: str,
        instance_public_id: str,
        idempotency_key: str,
    ) -> dict:
        idempotency_id = (task_public_id, idempotency_key)
        with self._lock:
            existing_public_id = self._idempotency.get(idempotency_id)
            if existing_public_id:
                existing = self._sessions[existing_public_id]
                return {
                    "session_public_id": existing["public_id"],
                    "task_public_id": existing["task_public_id"],
                    "student_public_id": existing["student_public_id"],
                    "instance_public_id": existing["instance_public_id"],
                    "token": "",
                    "replayed": True,
                }

            token = secrets.token_urlsafe(32)
            session = {
                "public_id": str(uuid.uuid4()),
                "task_public_id": task_public_id,
                "student_public_id": student_public_id,
                "instance_public_id": instance_public_id,
                "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                "revoked": False,
            }
            self._sessions[session["public_id"]] = session
            self._idempotency[idempotency_id] = session["public_id"]
            return {
                "session_public_id": session["public_id"],
                "task_public_id": task_public_id,
                "student_public_id": student_public_id,
                "instance_public_id": instance_public_id,
                "token": token,
                "replayed": False,
            }

    def renew(
        self,
        *,
        session_public_id: str,
        task_public_id: str,
        student_public_id: str,
        instance_public_id: str,
    ) -> dict:
        with self._lock:
            session = self._sessions.get(session_public_id)
            if session is None or session["revoked"] or not self._scope_matches(
                session,
                task_public_id=task_public_id,
                student_public_id=student_public_id,
                instance_public_id=instance_public_id,
            ):
                raise KeyError(session_public_id)

            token = secrets.token_urlsafe(32)
            session["token_hash"] = hashlib.sha256(token.encode()).hexdigest()
            return {
                "session_public_id": session["public_id"],
                "task_public_id": session["task_public_id"],
                "student_public_id": session["student_public_id"],
                "instance_public_id": session["instance_public_id"],
                "token": token,
            }

    def revoke(
        self,
        *,
        session_public_id: str,
        student_public_id: str,
    ) -> dict:
        with self._lock:
            session = self._sessions.get(session_public_id)
            if session is None or session["student_public_id"] != student_public_id:
                raise KeyError(session_public_id)

            session["revoked"] = True
            self._audit.append(
                {
                    "session_public_id": session_public_id,
                    "student_public_id": student_public_id,
                }
            )
            return {
                "session_public_id": session_public_id,
                "revoked": True,
                "audit_recorded": True,
            }

    def verify(
        self,
        *,
        token_hash: str,
        task_public_id: str,
        student_public_id: str,
        instance_public_id: str,
    ) -> dict:
        with self._lock:
            session = next(
                (
                    item
                    for item in self._sessions.values()
                    if item["token_hash"] == token_hash
                ),
                None,
            )
            if session is None:
                return self._invalid_verification()

            scope_matches = self._scope_matches(
                session,
                task_public_id=task_public_id,
                student_public_id=student_public_id,
                instance_public_id=instance_public_id,
            )
            return {
                "valid": scope_matches and not session["revoked"],
                "task_public_id": session["task_public_id"],
                "student_public_id": session["student_public_id"],
                "instance_public_id": session["instance_public_id"],
                "revoked": session["revoked"],
            }

    def snapshot(
        self,
        *,
        task_public_id: str,
        client_seq: int,
        payload: dict,
    ) -> dict:
        with self._lock:
            current_seq = self._snapshots.get(task_public_id, -1)
            if client_seq == current_seq:
                return {"confirmed_seq": current_seq, "idempotent_replay": True}
            if client_seq < current_seq:
                raise ValueError("client_seq is older than the latest snapshot")

            self._snapshots[task_public_id] = client_seq
            return {"confirmed_seq": client_seq, "idempotent_replay": False}

    def audit_facts(self) -> tuple[dict, ...]:
        with self._lock:
            return tuple(self._audit)

    def reset(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._idempotency.clear()
            self._snapshots.clear()
            self._audit.clear()

    @staticmethod
    def _invalid_verification() -> dict:
        return {
            "valid": False,
            "task_public_id": "",
            "student_public_id": "",
            "instance_public_id": "",
            "revoked": False,
        }

    @staticmethod
    def _scope_matches(
        session: dict,
        *,
        task_public_id: str,
        student_public_id: str,
        instance_public_id: str,
    ) -> bool:
        return (
            session["task_public_id"] == task_public_id
            and session["student_public_id"] == student_public_id
            and session["instance_public_id"] == instance_public_id
        )


fake_workspace_token_adapter = FakeWorkspaceTokenAdapter()
