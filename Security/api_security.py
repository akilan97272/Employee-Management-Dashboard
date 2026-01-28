"""
API SECURITY
============
Middleware bundle for API hardening.
"""

# FLOW:
# - Re-export HTTPS/XSS/insecure-connection middleware.
# WHY:
# - Centralizes API hardening components.
# HOW:
# - Provides a single import source for API middleware.

from __future__ import annotations

from Security.https_tls import HTTPSRedirectMiddleware, SecurityHeadersMiddleware
from Security.secure_connection import BlockInsecureRequestsMiddleware
from Security.xss_protection import XSSProtectionMiddleware

__all__ = [
    "HTTPSRedirectMiddleware",
    "SecurityHeadersMiddleware",
    "BlockInsecureRequestsMiddleware",
    "XSSProtectionMiddleware",
]
