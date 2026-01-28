"""
AUTH MODULE
===========
Centralized authentication wrapper for the application.

WHY:
- Keeps auth logic in one place for consistency.

HOW:
- Delegates to the secure authentication helper that verifies hashed passwords.
"""

from Security.authentication import authenticate_user

__all__ = ["authenticate_user"]