import bcrypt
import logging
import os
import secrets
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from .database import get_db
from .models import User

# ================= CONFIG =================
ALGORITHM = "HS256"
_PLACEHOLDER_SECRETS = {"", "CHANGE_THIS_SECRET", "change-this-secret", "AUTO_GENERATE"}
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"invalid-password", bcrypt.gensalt())
logger = logging.getLogger("app.auth")


def get_jwt_secret() -> str:
    secret = str(os.getenv("SECRET_KEY") or os.getenv("SESSION_SECRET_KEY") or "").strip()
    if secret in _PLACEHOLDER_SECRETS:
        secret = secrets.token_urlsafe(64)
        os.environ["SECRET_KEY"] = secret
        os.environ["SESSION_SECRET_KEY"] = secret
    return secret

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")


# ================= PASSWORD UTILS =================
def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def authenticate_user(db: Session, employee_id: str, password: str):

    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        # Constant-time style fallback to reduce account enumeration timing signals.
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_PASSWORD_HASH)
        logger.info("Authentication failed")
        return None
    if not verify_password(password, user.password_hash):
        logger.info("Authentication failed")
        return None
    logger.info("Authentication succeeded")
    return user


# ================= JWT AUTH (API / FUTURE WS) =================
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise credentials_exception

    return user


# ================= SESSION AUTH (DASHBOARD + CHAT) =================
def get_current_user_from_session(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
