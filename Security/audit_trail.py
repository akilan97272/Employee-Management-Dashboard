"""
AUDIT TRAIL
===========
Lightweight audit logging helper.
"""

# FLOW:
# - Call audit() on sensitive actions to emit structured audit events.
# WHY:
# - Provides accountability for critical actions.
# HOW:
# - Emits structured log lines for review.

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


logger = logging.getLogger("security.audit")
if not logger.handlers:
    os.makedirs("logs", exist_ok=True)
    handler = RotatingFileHandler("logs/audit.log", maxBytes=2_000_000, backupCount=3)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


def audit(event: str, user_id: int | None = None, details: str | None = None) -> None:
    logger.info("event=%s user_id=%s details=%s", event, user_id, details or "")
