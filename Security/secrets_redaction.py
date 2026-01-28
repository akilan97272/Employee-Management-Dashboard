"""
SECRETS REDACTION
=================
Utility to mask secrets in logs.
"""

# FLOW:
# - redact() masks common secret patterns before logging.
# WHY:
# - Prevents leaking credentials in logs.
# HOW:
# - Replaces sensitive values with ***.

from __future__ import annotations

import re


_SECRET_PATTERNS = [
    re.compile(r"(password=)([^&\s]+)", re.IGNORECASE),
    re.compile(r"(token=)([^&\s]+)", re.IGNORECASE),
    re.compile(r"(key=)([^&\s]+)", re.IGNORECASE),
]


def redact(value: str) -> str:
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(r"\1***", value)
    return value
