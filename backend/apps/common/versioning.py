"""Compatibility imports for Versioned/CAS primitives."""

from apps.core.versioning import (
    RevisionConflict,
    RevisionInputError,
    Versioned,
    assert_revision,
    build_etag,
    next_revision,
    parse_revision,
)

__all__ = [
    "RevisionConflict",
    "RevisionInputError",
    "Versioned",
    "assert_revision",
    "build_etag",
    "next_revision",
    "parse_revision",
]
