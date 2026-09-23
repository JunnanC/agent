from __future__ import annotations

"""Pure Versioned/CAS primitives.

The module does not know about Django models or databases.  A service locks
its aggregate, calls these functions, then persists the increment in its own
transaction.  That keeps the rule reusable for every future module.
"""

import re
from datetime import datetime
from typing import Protocol

from .errors import REVISION_CONFLICT, ApiError


class RevisionInputError(ValueError):
    """The client supplied a malformed revision or ETag."""


class Versioned(Protocol):
    row_version: int
    updated_at: datetime


class RevisionConflict(ApiError):
    def __init__(self, *, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            REVISION_CONFLICT,
            details=[
                {"field": "revision", "issue": "版本已过期"},
                {"expected": str(expected), "actual": str(actual)},
            ],
        )

    def __str__(self) -> str:
        return f"revision conflict: expected {self.expected}, actual {self.actual}"


_ETAG = re.compile(r'^(?:W/)?"?(\d+)"?$')


def parse_revision(value: str | int | None) -> int:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise RevisionInputError("revision is required")
    if isinstance(value, bool):
        raise RevisionInputError("revision must be an integer")
    if isinstance(value, int):
        revision = value
    else:
        match = _ETAG.fullmatch(value.strip())
        if match is None:
            raise RevisionInputError("revision must be a non-negative integer or ETag")
        revision = int(match.group(1))
    if revision < 0:
        raise RevisionInputError("revision must be non-negative")
    return revision


def assert_revision(actual: int, expected: int | str) -> None:
    current = parse_revision(actual)
    requested = parse_revision(expected)
    if current != requested:
        raise RevisionConflict(expected=requested, actual=current)


def next_revision(current: int) -> int:
    value = parse_revision(current)
    return value + 1


def build_etag(revision: int, *, weak: bool = False) -> str:
    value = f'"{parse_revision(revision)}"'
    return f"W/{value}" if weak else value
