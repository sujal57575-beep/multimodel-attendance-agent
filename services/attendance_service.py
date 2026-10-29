"""
services/attendance_service.py
Persists participant tracking results to the database.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from config import Config
from models.database import db_session, rows_to_list
from services.video_processor import ProcessingResult

logger = logging.getLogger(__name__)


class AttendanceService:

    def persist_results(self, result: ProcessingResult, session_start: datetime) -> int:
        """
        Write TrackedParticipant objects to DB.
        Returns count of attendance-marked participants.
        """
        marked = 0
        with db_session() as conn:
            for p in result.participants:
                pid = uuid.uuid4().hex
                ft = _offset_dt(session_start, p.first_time).isoformat()
                lt = _offset_dt(session_start, p.last_time).isoformat()
                needs_review = int(p.avg_confidence < 0.5 or p.frame_appearances < 3)

                face_verified_int = int(p.face_verified or p.face_detected_count >= Config.MIN_FACE_DETECTIONS)
                conn.execute(
                    """INSERT OR REPLACE INTO participants
                       (id, session_id, track_id, first_seen_at, last_seen_at,
                        total_duration_seconds, attendance_marked, confidence, needs_review,
                        face_verified, face_count, face_confidence)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        pid,
                        result.session_id,
                        p.track_id,
                        ft, lt,
                        round(p.total_duration, 2),
                        int(p.attendance_marked),
                        round(p.avg_confidence, 4),
                        needs_review,
                        face_verified_int,
                        p.face_detected_count,
                        round(p.avg_face_confidence, 4),
                    ),
                )
                # Attendance event
                if p.attendance_marked:
                    conn.execute(
                        """INSERT INTO attendance_events
                           (id, session_id, participant_id, event_type, timestamp, confidence)
                           VALUES (?,?,?,?,?,?)""",
                        (
                            uuid.uuid4().hex,
                            result.session_id,
                            pid,
                            "marked",
                            lt,
                            round(p.avg_confidence, 4),
                        ),
                    )
                    marked += 1

        logger.info(
            "Persisted %d participants, %d marked for session %s",
            len(result.participants), marked, result.session_id,
        )
        return marked

    def get_attendance(self, session_id: str) -> list[dict]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM participants WHERE session_id=? ORDER BY first_seen_at",
                (session_id,),
            ).fetchall()
        return rows_to_list(rows)

    def update_participant(self, participant_id: str, data: dict) -> bool:
        allowed = {"display_name", "student_id", "attendance_marked", "needs_review", "face_verified"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{k}=?" for k in updates)
        with db_session() as conn:
            conn.execute(
                f"UPDATE participants SET {set_clause} WHERE id=?",
                (*updates.values(), participant_id),
            )
        return True


def _offset_dt(base: datetime, seconds: float) -> datetime:
    from datetime import timedelta
    return base + timedelta(seconds=seconds)
