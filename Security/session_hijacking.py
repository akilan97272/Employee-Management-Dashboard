"""
SESSION HIJACKING PREVENTION
============================
Validates presence of session identifiers and fingerprint.
"""

# FLOW:
# - enforce_session_integrity() rejects missing/invalid session markers.
# WHY:
# - Reduces session fixation/hijacking risks.
# HOW:
# - Requires session id + fingerprint to be present.

from __future__ import annotations

from fastapi import HTTPException, status


def enforce_session_integrity(session: dict) -> None:
    """Ensure session has expected security markers."""
    if not session or "_sid" not in session or "_fp" not in session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalid",
        )
