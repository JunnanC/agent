"""Compatibility exports for core audit facts."""

from apps.core.audit import (
    AuditQueryFilters,
    AuditRecord,
    build_audit_queryset,
    hash_user_agent,
    mask_ip,
    record_audit,
)

__all__ = [
    "AuditQueryFilters",
    "AuditRecord",
    "build_audit_queryset",
    "hash_user_agent",
    "mask_ip",
    "record_audit",
]
