"""
FEATURE: AUTHENTICATION MIDDLEWARE
"""

# FLOW:
# - Re-export session middleware for auth-protected routes.
# WHY:
# - Keeps middleware imports minimal.
# HOW:
# - Exposes EncryptedSessionMiddleware.

from Security.session_security import EncryptedSessionMiddleware

__all__ = ["EncryptedSessionMiddleware"]
