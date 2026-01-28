"""
HEADERS HARDENING
=================
Extra hardening headers.
"""

# FLOW:
# - Middleware adds strict cross-origin and permissions headers.
# WHY:
# - Reduces browser-based attack surface.
# HOW:
# - Adds COOP/COEP/CORP and Permissions-Policy headers.

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware


class HeadersHardeningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Embedder-Policy", "require-corp")
        return response
