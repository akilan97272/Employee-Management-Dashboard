"""
DEPENDENCY SCANNING
===================
Guidance for automated vulnerability scanning of dependencies.

WHY:
- Detects vulnerable packages early and prevents known CVEs.

HOW:
- Use tools like pip-audit or safety in CI/CD pipelines.
- Keep requirements.txt pinned and update regularly.
"""

from __future__ import annotations


def scanning_recommendations() -> list[str]:
    return [
        "pip-audit -r requirements.txt",
        "safety check -r requirements.txt",
    ]
