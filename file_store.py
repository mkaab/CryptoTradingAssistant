import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# The system_files table schema:
# CREATE TABLE IF NOT EXISTS system_files (
#     filename VARCHAR(255) PRIMARY KEY,
#     content TEXT
# );

def _get_connection():
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    return psycopg2.connect(url)

def _init_db():
    conn = _get_connection()
    if conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_files (
                    filename VARCHAR(255) PRIMARY KEY,
                    content TEXT
                )
            """)
        conn.commit()
        conn.close()

# Initialize on import
_init_db()

def read_file(filename, default_content=""):
    """
    Reads a file's content from the Postgres system_files table.
    Falls back to the local filesystem if Postgres is not configured.
    """
    conn = _get_connection()
    if not conn:
        # Fallback to local
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return f.read()
        return default_content

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT content FROM system_files WHERE filename = %s", (filename,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return default_content
    finally:
        conn.close()

def write_file(filename, content, mode="w"):
    """
    Writes a file's content to the Postgres system_files table.
    Supports mode="w" (overwrite) and mode="a" (append).
    Falls back to the local filesystem if Postgres is not configured.
    """
    conn = _get_connection()
    if not conn:
        # Fallback to local
        with open(filename, mode, encoding="utf-8") as f:
            f.write(content)
        return

    try:
        with conn.cursor() as cursor:
            if mode == "a":
                cursor.execute("SELECT content FROM system_files WHERE filename = %s", (filename,))
                row = cursor.fetchone()
                existing = row[0] if row else ""
                content = existing + content
                
            cursor.execute("""
                INSERT INTO system_files (filename, content) 
                VALUES (%s, %s) 
                ON CONFLICT (filename) 
                DO UPDATE SET content = EXCLUDED.content
            """, (filename, content))
        conn.commit()
    finally:
        conn.close()
