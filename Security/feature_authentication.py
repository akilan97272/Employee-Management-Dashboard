"""
FEATURE: AUTHENTICATION
"""

# FLOW:
# - Re-export authentication and hashing helpers.
# WHY:
# - Simplifies imports for auth usage.
# HOW:
# - Re-exports hash/verify/auth functions.

from Security.authentication import authenticate_user
from Security.Password_hash import hash_password, verify_password

__all__ = ["authenticate_user", "hash_password", "verify_password"]
