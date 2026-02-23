from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import dotenv
import os
dotenv.load_dotenv()

# Import cloud MariaDB connection URL for reference (not used directly)
from app.cloud_database import CLOUD_DATABASE_URL

# Always use DATABASE_URL from .env file
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set in your .env file.")

# Auto-detect if the URL is local or cloud
def is_local_database(url):
    return (
        url is not None and (
            "localhost" in url or
            "127.0.0.1" in url
        )
    )

IS_LOCAL_DB = is_local_database(DATABASE_URL)

engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SEC", "1800")),
    "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT_SEC", "30")),
    "pool_use_lifo": os.getenv("DB_POOL_USE_LIFO", "true").strip().lower() in {"1", "true", "yes", "on"},
}
if DATABASE_URL.startswith(("mysql://", "mysql+pymysql://", "mariadb://", "mariadb+pymysql://", "postgresql://", "postgresql+psycopg2://")):
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "20"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "30"))
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_team_info(db, user_id):
    team = db.execute(
        text(
            """
            SELECT
                t.name,
                leader.name,
                leader.active_leader
            FROM teams t
            JOIN users leader ON leader.id = t.leader_id
            WHERE t.id = (
                SELECT current_team_id FROM users WHERE id=:user_id
            )
            """
        ),
        {"user_id": user_id},
    ).fetchone()

    members = db.execute(
        text(
            """
            SELECT name FROM users
            WHERE current_team_id = (
                SELECT current_team_id FROM users WHERE id=:user_id
            )
            """
        ),
        {"user_id": user_id},
    ).fetchall()

    if not team:
        return {
            "team_name": None,
            "leader": None,
            "is_acting": False,
            "members": [m[0] for m in members],
        }

    return {
        "team_name": team[0],
        "leader": team[1],
        "is_acting": bool(team[2]),
        "members": [m[0] for m in members]
    }
