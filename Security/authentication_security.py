"""
AUTHENTICATION SECURITY
=======================
Centralized authentication helpers.
"""

from __future__ import annotations

from Security.authentication import authenticate_user


# FLOW:
# - Re-export authenticate_user/hash helpers for clean imports.
# WHY:
# - Keeps authentication logic in one place.
# HOW:
# - Imports and re-exports core auth helpers.
__all__ = ["authenticate_user"]
