"""
AUTHORIZATION SECURITY
======================
RBAC enforcement helpers.
"""

# FLOW:
# - Re-export enforce_rbac to protect routes by role.
# WHY:
# - Prevents users from accessing unauthorized pages.
# HOW:
# - Role checks are centralized in enforce_rbac().

from __future__ import annotations

from Security.rbac import enforce_rbac

__all__ = ["enforce_rbac"]
