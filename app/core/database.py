import os
from contextlib import contextmanager
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("AIPS_DB_HOST", "localhost"),
    "port": int(os.getenv("AIPS_DB_PORT", "5432")),
    "database": os.getenv("AIPS_DB_NAME", "aips_db"),
    "user": os.getenv("AIPS_DB_USER", "aips"),
    "password": os.getenv("AIPS_DB_PASSWORD", "aips123"),
}

_connection_pool = pool.SimpleConnectionPool(minconn=1, maxconn=10, **DB_CONFIG)

@contextmanager
def get_conn():
    conn = _connection_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _connection_pool.putconn(conn)

def fetch_all(sql: str, params: tuple = ()):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

def fetch_one(sql: str, params: tuple = ()):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone()

def execute_returning_id(sql: str, params: tuple = (), id_column: str = "id"):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row[id_column] if row else None

def execute(sql: str, params: tuple = ()):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
