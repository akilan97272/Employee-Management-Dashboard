from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import dotenv
import os
from Security.database_security import safe_execute


def _env_name() -> str:
    env = os.getenv("APP_ENV", "").strip().lower()
    if env in {"prod", "production"}:
        return ".env.production"
    if env in {"local", "localhost", "dev", "development"}:
        return ".env.localhost"

    root = os.path.dirname(__file__)
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
    root = os.path.dirname(__file__)
    return os.path.join(root, _env_name())


dotenv.load_dotenv(_env_path())

# Database connection (fallback to local SQLite if not provided)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./attendance.db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_user_hash_columns():
    """Ensure users table has email_hash and rfid_hash columns for legacy DBs."""
    # Only applies to MySQL/MariaDB where information_schema is available
    if engine.dialect.name not in {"mysql", "mariadb"}:
        return
    with engine.begin() as conn:
        tables = conn.execute(text("SHOW TABLES")).fetchall()
        table_names = {row[0] for row in tables}
        if "users" not in table_names:
            return

        rows = conn.execute(
            text(
                """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'users'
                """
            )
        ).fetchall()
        existing = {row[0] for row in rows}

        if "email_hash" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN email_hash VARCHAR(64) NULL"))
        if "rfid_hash" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN rfid_hash VARCHAR(64) NULL"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_team_info(db, user_id):
    team = safe_execute(db, """
        SELECT
            t.name,
            leader.name,
            leader.active_leader
        FROM teams t
        JOIN users leader ON leader.id = t.leader_id
        WHERE t.id = (
            SELECT current_team_id FROM users WHERE id=:user_id
        )
    """, {"user_id": user_id}).fetchone()

    members = safe_execute(db, """
        SELECT name FROM users
        WHERE current_team_id = (
            SELECT current_team_id FROM users WHERE id=:user_id
        )
    """, {"user_id": user_id}).fetchall()

    return {
        "team_name": team[0],
        "leader": team[1],
        "is_acting": bool(team[2]),
        "members": [m[0] for m in members]
    }
