"""
FEATURE: RATE LIMITING
"""

# FLOW:
# - Re-export create_login_limiter for login throttling.
# WHY:
# - Simplifies rate limiter usage across the app.
# HOW:
# - Re-exports create_login_limiter.

from Security.login_attempt_limiting import create_login_limiter

__all__ = ["create_login_limiter"]
