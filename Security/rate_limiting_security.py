"""
RATE LIMITING SECURITY
======================
Login attempt limiting wrapper.
"""

# FLOW:
# - Re-export create_login_limiter for clean imports.
# WHY:
# - Standardizes login throttling across the project.
# HOW:
# - Centralized factory returns limiter with config.

from __future__ import annotations

from Security.login_attempt_limiting import create_login_limiter

__all__ = ["create_login_limiter"]
