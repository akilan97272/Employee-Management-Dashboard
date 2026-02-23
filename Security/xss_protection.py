"""
XSS PROTECTION
==============
Security headers and CSP for mitigating cross-site scripting.
"""

# FLOW:
# - Middleware applies CSP and XSS-related headers to responses.
# WHY:
# - Mitigates script injection and clickjacking.
# HOW:
# - Applies CSP and restrictive headers on every response.

from __future__ import annotations

import os
from starlette.middleware.base import BaseHTTPMiddleware


class XSSProtectionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "no-referrer-when-downgrade")

        app_profile = os.getenv("APP_PROFILE", "development").strip().lower()
        is_production_profile = app_profile in {"prod", "production"}
        allow_unsafe_eval = os.getenv(
            "CSP_ALLOW_UNSAFE_EVAL",
            "false" if is_production_profile else "true",
        ).strip().lower() in {"1", "true", "yes", "on"}
        script_policy = "script-src 'self' 'unsafe-inline' https:;"
        if allow_unsafe_eval:
            script_policy = "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:;"

        csp = (
            "default-src 'self' https:; "
            f"{script_policy} "
            "style-src 'self' 'unsafe-inline' https:; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data: https:; "
            "connect-src 'self' blob: https:; "
            "worker-src 'self' blob: https:; "
            "frame-ancestors 'self'"
        )
        response.headers.setdefault("Content-Security-Policy", csp)
        return response
