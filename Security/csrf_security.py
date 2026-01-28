"""
CSRF SECURITY
=============
CSRF middleware wrapper.
"""

# FLOW:
# - Re-export CSRFMiddleware for easy imports.
# WHY:
# - Keeps CSRF wiring consistent across the project.
# HOW:
# - Re-exports CSRFMiddleware for startup wiring.

from __future__ import annotations

from Security.csrf_protection import CSRFMiddleware

__all__ = ["CSRFMiddleware"]
