"""
scripts/initialize_db.py — DB init + optional demo data seeding
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import json
import random
from datetime import datetime, timedelta

from config import Config
from models.database import init_db, db_session

Config.ensure_dirs()
init_db()
print(f"[OK] Database initialised at {Config.DATABASE_PATH}")

SEED = "--seed" in sys.argv

if SEED:
    print("Seeding demo data…")
    subjects = ["Machine Learning", "Data Structures", "Linear Algebra", "Python Basics"]
    instructors = ["Dr. Patel", "Prof. Johnson", "Ms. Chen", "Mr. García"]

    with db_session() as conn:
        for i in range(6):
            sid = uuid.uuid4().hex
            started = datetime.utcnow() - timedelta(days=i * 3, hours=random.randint(0,8))
            ended   = started + timedelta(hours=1, minutes=random.randint(0,30))
            conn.execute(
                """INSERT INTO sessions
                   (id, name, subject, instructor, location, started_at, ended_at,
                    status, total_frames, fps, duration_seconds, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    sid,
                    f"Session {i+1} — {subjects[i % len(subjects)]}",
                    subjects[i % len(subjects)],
                    instructors[i % len(instructors)],
                    f"Room {100 + i}",
                    started.isoformat(),
                    ended.isoformat(),
                    "completed",
                    random.randint(3000, 9000),
                    25.0,
                    random.uniform(3000, 5400),
                    started.isoformat(),
                ),
            )

            # Participants
            num_p = random.randint(12, 30)
            for j in range(num_p):
                pid  = uuid.uuid4().hex
                dur  = random.uniform(60, 4000)
                conn.execute(
                    """INSERT INTO participants
                       (id, session_id, track_id, first_seen_at, last_seen_at,
                        total_duration_seconds, attendance_marked, confidence, needs_review)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        pid, sid, f"T{j:04d}",
                        started.isoformat(),
                        (started + timedelta(seconds=dur)).isoformat(),
                        round(dur, 2),
                        1 if dur >= Config.ATTENDANCE_THRESHOLD_SECONDS else 0,
                        round(random.uniform(0.45, 0.98), 4),
                        1 if random.random() < 0.1 else 0,
                    ),
                )

            # Engagement windows (1 per minute)
            n_windows = max(1, int((ended - started).seconds // Config.ENGAGEMENT_WINDOW_SECONDS))
            for w in range(n_windows):
                ws = started + timedelta(seconds=w * Config.ENGAGEMENT_WINDOW_SECONDS)
                we = ws + timedelta(seconds=Config.ENGAGEMENT_WINDOW_SECONDS)
                p_score = round(random.uniform(0.3, 0.95), 4)
                m_score = round(random.uniform(0.1, 0.7), 4)
                a_score = round(random.uniform(0.2, 0.85), 4)
                h_score = round(p_score * random.uniform(0.7, 1.0), 4)
                comp    = round((p_score*0.35 + m_score*0.25 + a_score*0.25 + h_score*0.15), 4)
                conn.execute(
                    """INSERT INTO engagement_metrics
                       (id,session_id,window_start,window_end,window_index,
                        presence_score,motion_score,audio_score,head_pose_score,
                        composite_score,participant_count,audio_activity_seconds,
                        silence_seconds,missing_data,confidence)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        uuid.uuid4().hex, sid,
                        ws.isoformat(), we.isoformat(), w,
                        p_score, m_score, a_score, h_score, comp,
                        num_p, round(random.uniform(20, 55), 2),
                        round(random.uniform(5, 40), 2),
                        json.dumps([]),
                        round(random.uniform(0.65, 1.0), 4),
                    ),
                )

            # Recommendations
            conn.execute(
                """INSERT INTO recommendations
                   (id,session_id,title,observation,evidence,suggestion,confidence,time_range,source,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    uuid.uuid4().hex, sid,
                    "Demo Recommendation",
                    "This is sample data for dashboard demonstration.",
                    json.dumps({"demo": True}),
                    "Replace with real session data by uploading a class recording.",
                    0.9,
                    json.dumps({}),
                    "rule",
                    datetime.utcnow().isoformat(),
                ),
            )

    print("[OK] Demo data seeded: 6 sessions with participants, engagement, and recommendations")
    print("  NOTE: All demo data is clearly labelled. Run without --seed for real sessions only.")
else:
    print("Run with --seed to insert demo/sample data for dashboard testing.")
