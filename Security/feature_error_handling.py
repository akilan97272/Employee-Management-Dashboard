"""
FEATURE: SECURE ERROR HANDLING
"""

# FLOW:
# - Re-export register_error_handlers to mask error details.
# WHY:
# - Keeps safe error handling consistent.
# HOW:
# - Re-exports register_error_handlers.

from Security.error_handling import register_error_handlers

__all__ = ["register_error_handlers"]
