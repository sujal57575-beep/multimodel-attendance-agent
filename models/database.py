"""
models/database.py — SQLite schema creation & connection management
Multimodal Attendance & Engagement Agent
"""

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)

DDL = """
-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    subject         TEXT,
    instructor      TEXT,
    location        TEXT,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    status          TEXT NOT NULL DEFAULT 'active',   -- active | processing | completed | error
    video_path      TEXT,
    audio_path      TEXT,
    total_frames    INTEGER DEFAULT 0,
    fps             REAL DEFAULT 0,
    duration_seconds REAL DEFAULT 0,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Participants (anonymous by default)
CREATE TABLE IF NOT EXISTS participants (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    track_id        TEXT NOT NULL,           -- OpenCV tracker ID
    display_name    TEXT,                    -- optional, manually assigned
    student_id      TEXT,                    -- optional, institution ID
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    total_duration_seconds REAL DEFAULT 0,
    attendance_marked INTEGER DEFAULT 0,     -- 0 | 1
    confidence      REAL DEFAULT 1.0,        -- detection confidence
    needs_review    INTEGER DEFAULT 0,
    face_verified   INTEGER DEFAULT 0,       -- 0 | 1 (verified by face detector)
    face_count      INTEGER DEFAULT 0,       -- number of frames with face detected
    face_confidence REAL DEFAULT 0.0,        -- average face confidence
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Attendance events (individual presence windows)
CREATE TABLE IF NOT EXISTS attendance_events (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    participant_id  TEXT NOT NULL,
    event_type      TEXT NOT NULL,           -- appeared | disappeared | marked
    timestamp       TEXT NOT NULL,
    frame_number    INTEGER,
    confidence      REAL DEFAULT 1.0,
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (participant_id) REFERENCES participants(id)
);

-- Engagement metrics (time-windowed)
CREATE TABLE IF NOT EXISTS engagement_metrics (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    window_start    TEXT NOT NULL,
    window_end      TEXT NOT NULL,
    window_index    INTEGER NOT NULL,
    presence_score  REAL DEFAULT 0,
    motion_score    REAL DEFAULT 0,
    audio_score     REAL DEFAULT 0,
    head_pose_score REAL DEFAULT 0,
    composite_score REAL DEFAULT 0,
    participant_count INTEGER DEFAULT 0,
    audio_activity_seconds REAL DEFAULT 0,
    silence_seconds REAL DEFAULT 0,
    missing_data    TEXT,                    -- JSON list of missing signals
    confidence      REAL DEFAULT 1.0,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- AI / rule-based recommendations
CREATE TABLE IF NOT EXISTS recommendations (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    title           TEXT NOT NULL,
    observation     TEXT NOT NULL,
    evidence        TEXT NOT NULL,           -- JSON
    suggestion      TEXT NOT NULL,
    confidence      REAL DEFAULT 0.5,
    time_range      TEXT,                    -- JSON {start, end}
    source          TEXT DEFAULT 'rule',     -- rule | gemini | local_llm
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Media files
CREATE TABLE IF NOT EXISTS media_files (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    file_type       TEXT NOT NULL,           -- video | audio | report | generated_audio | generated_code
    original_name   TEXT,
    stored_path     TEXT NOT NULL,
    file_size_bytes INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    delete_after    TEXT,                    -- ISO date, optional
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_logs (
    id              TEXT PRIMARY KEY,
    action          TEXT NOT NULL,
    entity_type     TEXT,
    entity_id       TEXT,
    actor           TEXT DEFAULT 'system',
    details         TEXT,                    -- JSON
    ip_address      TEXT,
    timestamp       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_participants_session ON participants(session_id);
CREATE INDEX IF NOT EXISTS idx_attendance_session   ON attendance_events(session_id);
CREATE INDEX IF NOT EXISTS idx_engagement_session   ON engagement_metrics(session_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_session ON recommendations(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_action         ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp      ON audit_logs(timestamp);
"""


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row-factory set."""
    conn = sqlite3.connect(Config.DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_session():
    """Context manager for automatic commit / rollback."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist, and migrate columns if needed."""
    Path(Config.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with db_session() as conn:
        conn.executescript(DDL)
        # Migrate participants columns if database already existed
        cursor = conn.execute("PRAGMA table_info(participants)")
        cols = {row["name"] for row in cursor.fetchall()}
        if "face_verified" not in cols:
            conn.execute("ALTER TABLE participants ADD COLUMN face_verified INTEGER DEFAULT 0")
        if "face_count" not in cols:
            conn.execute("ALTER TABLE participants ADD COLUMN face_count INTEGER DEFAULT 0")
        if "face_confidence" not in cols:
            conn.execute("ALTER TABLE participants ADD COLUMN face_confidence REAL DEFAULT 0.0")
    logger.info("Database initialised at %s", Config.DATABASE_PATH)


def row_to_dict(row) -> dict:
    """Convert sqlite3.Row to plain dict."""
    return dict(row) if row else {}


def rows_to_list(rows) -> list:
    """Convert list of sqlite3.Row to list of dicts."""
    return [dict(r) for r in rows]
