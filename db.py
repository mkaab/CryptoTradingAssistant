"""
Shared database engine singleton.
All modules import get_engine() from here instead of defining their own.
"""
import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

DB_FILE = "market_data.db"

_engine = None

def get_engine():
    """
    Returns a singleton SQLAlchemy engine.
    Uses DATABASE_URL (Postgres) in production, falls back to SQLite locally.
    The engine maintains its own internal connection pool.
    """
    global _engine
    if _engine is None:
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            # Railway uses postgres:// but SQLAlchemy requires postgresql://
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            _engine = create_engine(db_url, pool_size=5, max_overflow=10, pool_pre_ping=True)
        else:
            _engine = create_engine(f"sqlite:///{DB_FILE}")
    return _engine

def is_postgres():
    """Returns True if we are connected to Postgres (production)."""
    return os.environ.get("DATABASE_URL") is not None
