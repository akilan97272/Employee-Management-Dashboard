"""
SECURE USER AUTHENTICATION
==========================
Authenticate users using hashed credentials.

FLOW:
- Query user by username.
- Verify password hash.
- Return user on success.

WHY:
- Ensures only valid users can access the system.

HOW:
- Uses Argon2 hashes to verify passwords without storing raw secrets.
"""

from sqlalchemy.orm import Session, load_only
from models import User
from Security.Password_hash import verify_password


def authenticate_user(db: Session, username: str, password: str):
    """Authenticate user by verifying username and password hash."""
    username = (username or "").strip()
    user = (
        db.query(User)
        .options(load_only(User.id, User.employee_id, User.password_hash, User.role))
        .filter(User.employee_id == username)
        .first()
    )
    if user and verify_password(password, user.password_hash):
        return user
    return None
