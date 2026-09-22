"""Compatibility exports for the core error catalogue.

Business modules may keep importing ``apps.common.errors`` during the
compatibility window; new code should import from ``apps.core.errors``.
"""

from apps.core.errors import *
