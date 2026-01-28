"""
FEATURE: ROLE-BASED ACCESS CONTROL
"""

# FLOW:
# - Re-export enforce_rbac for role checks.
# WHY:
# - Keeps role checks centralized.
# HOW:
# - Re-exports enforce_rbac.

from Security.rbac import enforce_rbac

__all__ = ["enforce_rbac"]
