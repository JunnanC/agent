"""Compatibility imports for append-only fact primitives."""

from apps.core.append_only import AppendOnly, AppendOnlyViolation, Fact, FactStore, append_once

__all__ = ["AppendOnly", "AppendOnlyViolation", "Fact", "FactStore", "append_once"]
