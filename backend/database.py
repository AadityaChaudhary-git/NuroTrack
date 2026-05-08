"""
NuroTrack — Database Layer
Handles SQLite connection (thread-safe) and schema initialization.
"""

import os
import sqlite3
import threading
from config import DB_PATH

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection, creating it if needed."""
    if not hasattr(_local, 'conn') or _local.conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn.execute("PRAGMA cache_size=-8000")
    return _local.conn


def init_db():
    """Create all tables if they don't already exist."""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      TEXT NOT NULL,
            app          TEXT NOT NULL,
            window_title TEXT,
            start_time   TEXT NOT NULL,
            end_time     TEXT,
            duration_sec INTEGER DEFAULT 0,
            category     TEXT DEFAULT 'neutral',
            synced       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS hourly_stats (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             TEXT NOT NULL,
            hour             INTEGER NOT NULL,
            productive_sec   INTEGER DEFAULT 0,
            neutral_sec      INTEGER DEFAULT 0,
            unproductive_sec INTEGER DEFAULT 0,
            nuro_score       REAL DEFAULT 0,
            cognitive_load   TEXT DEFAULT 'low',
            UNIQUE(date, hour)
        );
        CREATE TABLE IF NOT EXISTS daily_reports (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             TEXT UNIQUE NOT NULL,
            active_sec       INTEGER DEFAULT 0,
            productive_sec   INTEGER DEFAULT 0,
            neutral_sec      INTEGER DEFAULT 0,
            unproductive_sec INTEGER DEFAULT 0,
            top_app          TEXT,
            nuro_score       REAL DEFAULT 0,
            cognitive_state  TEXT DEFAULT 'neutral',
            burnout_risk     REAL DEFAULT 0,
            apps_count       INTEGER DEFAULT 0,
            synced           INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    print(f"[DB] SQLite ready at {DB_PATH}")
