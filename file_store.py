"""
Virtual File System — stores text files in Postgres instead of the local disk.
Falls back to local filesystem when DATABASE_URL is not set (local dev).
"""
import os
from db import get_engine, is_postgres
from sqlalchemy import text

def _init_db():
    """Create the system_files table if it doesn't exist."""
    if not is_postgres():
        return
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS system_files (
                filename VARCHAR(255) PRIMARY KEY,
                content TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))

# Initialize on import
_init_db()

def read_file(filename, default_content=""):
    """
    Reads a file's content from the Postgres system_files table.
    Falls back to the local filesystem if Postgres is not configured.
    """
    if not is_postgres():
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return f.read()
        return default_content

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT content FROM system_files WHERE filename = :f"),
            {"f": filename}
        )
        row = result.fetchone()
        if row:
            return row[0]
        return default_content

def write_file(filename, content, mode="w"):
    """
    Writes a file's content to the Postgres system_files table.
    Supports mode="w" (overwrite) and mode="a" (append).
    Falls back to the local filesystem if Postgres is not configured.
    """
    if not is_postgres():
        with open(filename, mode, encoding="utf-8") as f:
            f.write(content)
        return

    engine = get_engine()
    with engine.begin() as conn:
        if mode == "a":
            result = conn.execute(
                text("SELECT content FROM system_files WHERE filename = :f"),
                {"f": filename}
            )
            row = result.fetchone()
            existing = row[0] if row else ""
            content = existing + content
            
        conn.execute(text("""
            INSERT INTO system_files (filename, content, updated_at) 
            VALUES (:f, :c, NOW()) 
            ON CONFLICT (filename) 
            DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()
        """), {"f": filename, "c": content})
