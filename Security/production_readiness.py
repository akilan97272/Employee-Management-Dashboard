"""
PRODUCTION READINESS
====================
Utilities for logging and safe error handling.
"""

# FLOW:
# - register_error_handlers(app) masks errors.
# - ActivityLoggingMiddleware logs requests.
# WHY:
# - Stabilizes production behavior and diagnostics.
# HOW:
# - Applies logging and safe error responses at startup.

from __future__ import annotations

from Security.activity_logging import ActivityLoggingMiddleware
from Security.error_handling import register_error_handlers

__all__ = ["ActivityLoggingMiddleware", "register_error_handlers"]
