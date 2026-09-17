from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.db import connection


def _execute(sql: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(sql)


def _drop_tables() -> None:
    _execute("DROP TABLE IF EXISTS audit_logs")
    _execute("DROP TABLE IF EXISTS outbox_events")


def _create_tables() -> None:
    _execute(
        """
        CREATE TABLE outbox_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id VARCHAR(36) NOT NULL UNIQUE,
            event_type VARCHAR(64) NOT NULL,
            aggregate_type VARCHAR(64) NOT NULL,
            aggregate_id VARCHAR(64) NOT NULL,
            assignment_id VARCHAR(64) NULL,
            instance_id VARCHAR(64) NULL,
            topic VARCHAR(128) NOT NULL,
            payload_json JSON NOT NULL,
            status VARCHAR(16) NOT NULL,
            attempt_count INTEGER UNSIGNED NOT NULL DEFAULT 0,
            available_at DATETIME NOT NULL,
            published_at DATETIME NULL,
            last_error LONGTEXT NOT NULL DEFAULT '',
            trace_id VARCHAR(128) NOT NULL,
            created_at DATETIME NOT NULL
        )
        """
    )
    _execute(
        """
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id VARCHAR(64) NULL,
            actor_role_code VARCHAR(32) NULL,
            action VARCHAR(64) NOT NULL,
            target_type VARCHAR(32) NOT NULL,
            target_id VARCHAR(64) NOT NULL,
            assignment_id VARCHAR(64) NULL,
            instance_id VARCHAR(64) NULL,
            trace_id VARCHAR(128) NOT NULL,
            request_id VARCHAR(36) NOT NULL,
            idempotency_key VARCHAR(64) NULL,
            result VARCHAR(8) NOT NULL,
            reason LONGTEXT NOT NULL DEFAULT '',
            before_json JSON NULL,
            after_json JSON NULL,
            ip VARCHAR(64) NOT NULL DEFAULT '',
            user_agent_hash CHAR(64) NULL,
            occurred_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL
        )
        """
    )


@pytest.fixture
def common_tables(db: None) -> Iterator[None]:
    _drop_tables()
    _create_tables()
    try:
        yield
    finally:
        _drop_tables()
