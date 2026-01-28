"""
FEATURE: CSRF PROTECTION
"""

# FLOW:
# - Re-export CSRFMiddleware for secure form submissions.
# WHY:
# - Standardizes CSRF protection imports.
# HOW:
# - Re-exports CSRFMiddleware.

from Security.csrf_protection import CSRFMiddleware

__all__ = ["CSRFMiddleware"]
