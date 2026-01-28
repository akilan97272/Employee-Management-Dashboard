"""
Backfill encryption for existing rows.
Requires DATA_ENCRYPTION_KEY to be set.
"""

from __future__ import annotations

import dotenv
import os

from sqlalchemy.orm.attributes import flag_modified

from database import SessionLocal
from models import (
    User,
    Attendance,
    RemovedEmployee,
    UnknownRFID,
    Room,
    Department,
    Task,
    LeaveRequest,
    Team,
)
from Security.data_integrity import sha256_hex
from Security.key_management import get_aes256_key


def _env_name() -> str:
    env = os.getenv("APP_ENV", "").strip().lower()
    if env in {"prod", "production"}:
        return ".env.production"
    if env in {"local", "localhost", "dev", "development"}:
        return ".env.localhost"

    root = os.path.dirname(os.path.dirname(__file__))
    prod_path = os.path.join(root, ".env.production")
    local_path = os.path.join(root, ".env.localhost")

    def _is_active(path: str) -> bool:
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("ENV_ACTIVE="):
                    return line.split("=", 1)[1].strip().strip('"').lower() == "true"
        return False

    if _is_active(prod_path):
        return ".env.production"
    return ".env.localhost"


def _env_path() -> str:
    root = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(root, _env_name())


dotenv.load_dotenv(_env_path())


def touch_fields(obj, fields):
    for field in fields:
        setattr(obj, field, getattr(obj, field))
        flag_modified(obj, field)


def migrate_users(db):
    users = db.query(User).all()
    for user in users:
        if user.email and not user.email_hash:
            user.email_hash = sha256_hex(user.email.lower())
            flag_modified(user, "email_hash")
        if user.rfid_tag and not user.rfid_hash:
            user.rfid_hash = sha256_hex(user.rfid_tag)
            flag_modified(user, "rfid_hash")
        touch_fields(user, ["name", "email", "rfid_tag", "department"])


def migrate_removed(db):
    rows = db.query(RemovedEmployee).all()
    for row in rows:
        touch_fields(row, ["name", "email", "rfid_tag", "department"])


def migrate_unknown(db):
    rows = db.query(UnknownRFID).all()
    for row in rows:
        touch_fields(row, ["rfid_tag", "location"])


def migrate_rooms(db):
    rows = db.query(Room).all()
    for row in rows:
        touch_fields(row, ["description"])


def migrate_departments(db):
    rows = db.query(Department).all()
    for row in rows:
        touch_fields(row, ["description"])


def migrate_tasks(db):
    rows = db.query(Task).all()
    for row in rows:
        touch_fields(row, ["title", "description"])


def migrate_leaves(db):
    rows = db.query(LeaveRequest).all()
    for row in rows:
        touch_fields(row, ["reason"])


def migrate_teams(db):
    rows = db.query(Team).all()
    for row in rows:
        touch_fields(row, ["name", "department"])


def main():
    _ = get_aes256_key()
    db = SessionLocal()
    try:
        migrate_users(db)
        migrate_removed(db)
        migrate_unknown(db)
        migrate_rooms(db)
        migrate_departments(db)
        migrate_tasks(db)
        migrate_leaves(db)
        migrate_teams(db)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()