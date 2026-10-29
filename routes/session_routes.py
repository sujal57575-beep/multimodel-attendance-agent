"""
routes/session_routes.py — Session CRUD + video upload + async processing
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app

from models.database import db_session, rows_to_list, row_to_dict
from services.video_processor import VideoProcessor
from services.audio_processor import AudioProcessor
from services.attendance_service import AttendanceService
from services.engagement_service import EngagementService
from services.recommendation_service import RecommendationService
from services.multimodal_agent import MultimodalAttendanceAgent
from utils.file_utils import save_upload
from utils.validators import require_fields, sanitize_text
from config import Config

bp = Blueprint("sessions", __name__, url_prefix="/api/sessions")
logger = logging.getLogger(__name__)

# In-memory progress store {session_id: {pct, status, error}}
_progress: dict[str, dict] = {}


# ── List / Create ─────────────────────────────────────────────────────────────

@bp.route("", methods=["GET"])
def list_sessions():
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    return jsonify({"sessions": rows_to_list(rows)}), 200


@bp.route("", methods=["POST"])
def create_session():
    data = request.get_json(force=True, silent=True) or {}
    missing = require_fields(data, ["name"])
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    sid = uuid.uuid4().hex
    now = datetime.utcnow().isoformat()
    with db_session() as conn:
        conn.execute(
            """INSERT INTO sessions (id, name, subject, instructor, location, started_at, status, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                sid,
                sanitize_text(data["name"], 200),
                sanitize_text(data.get("subject", ""), 200),
                sanitize_text(data.get("instructor", ""), 200),
                sanitize_text(data.get("location", ""), 200),
                now, "active", now,
            ),
        )
        _audit(conn, "session_created", "session", sid, data.get("instructor", "system"))

    return jsonify({"session_id": sid, "status": "active", "created_at": now}), 201


# ── Single Session ────────────────────────────────────────────────────────────

@bp.route("/<session_id>", methods=["GET"])
def get_session(session_id: str):
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    if not row:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(row_to_dict(row)), 200


@bp.route("/<session_id>", methods=["PATCH"])
def update_session(session_id: str):
    data = request.get_json(force=True, silent=True) or {}
    allowed = {"name", "subject", "instructor", "location", "notes", "status"}
    updates = {k: sanitize_text(str(v)) for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with db_session() as conn:
        conn.execute(
            f"UPDATE sessions SET {set_clause} WHERE id=?",
            (*updates.values(), session_id),
        )
    return jsonify({"updated": True}), 200


@bp.route("/<session_id>", methods=["DELETE"])
def delete_session(session_id: str):
    with db_session() as conn:
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        conn.execute("DELETE FROM participants WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM attendance_events WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM engagement_metrics WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM recommendations WHERE session_id=?", (session_id,))
        _audit(conn, "session_deleted", "session", session_id)
    return jsonify({"deleted": True}), 200


# ── Video Upload ──────────────────────────────────────────────────────────────

@bp.route("/<session_id>/video", methods=["POST"])
def upload_video(session_id: str):
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    try:
        meta = save_upload(f, session_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422

    media_id = uuid.uuid4().hex
    with db_session() as conn:
        conn.execute(
            """INSERT INTO media_files (id, session_id, file_type, original_name, stored_path, file_size_bytes, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (media_id, session_id, "video", meta["original_name"],
             meta["stored_path"], meta["file_size_bytes"], datetime.utcnow().isoformat()),
        )
        conn.execute(
            "UPDATE sessions SET video_path=? WHERE id=?",
            (meta["stored_path"], session_id),
        )

    return jsonify({"media_id": media_id, **meta}), 201


# ── Processing ────────────────────────────────────────────────────────────────

@bp.route("/<session_id>/process", methods=["POST"])
def start_processing(session_id: str):
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    if not row:
        return jsonify({"error": "Session not found"}), 404

    session = row_to_dict(row)
    if not session.get("video_path"):
        return jsonify({"error": "No video uploaded for this session"}), 422

    _progress[session_id] = {"pct": 0, "status": "queued", "error": None}

    thread = threading.Thread(
        target=_run_processing,
        args=(session_id, session),
        daemon=True,
    )
    thread.start()

    return jsonify({"status": "processing_started", "session_id": session_id}), 202


@bp.route("/<session_id>/progress", methods=["GET"])
def get_progress(session_id: str):
    prog = _progress.get(session_id, {"pct": 0, "status": "unknown", "error": None})
    return jsonify(prog), 200


# ── Background processing task ────────────────────────────────────────────────

def _run_processing(session_id: str, session: dict):
    def progress_cb(pct, msg):
        _progress[session_id] = {"pct": pct, "status": msg, "error": None}

    try:
        _progress[session_id]["status"] = "starting"

        with db_session() as conn:
            conn.execute(
                "UPDATE sessions SET status='processing' WHERE id=?", (session_id,)
            )

        agent = MultimodalAttendanceAgent()
        session_start = datetime.fromisoformat(session["started_at"])
        pipeline_output = agent.run_session_pipeline(
            session_id=session_id,
            video_path=session["video_path"],
            session_start=session_start,
            progress_cb=progress_cb,
        )

        metrics = pipeline_output["engagement_metrics"]
        with db_session() as conn:
            for m in metrics:
                conn.execute(
                    """INSERT OR REPLACE INTO engagement_metrics
                       (id,session_id,window_start,window_end,window_index,
                        presence_score,motion_score,audio_score,head_pose_score,
                        composite_score,participant_count,audio_activity_seconds,
                        silence_seconds,missing_data,confidence)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        m["id"], m["session_id"], m["window_start"], m["window_end"],
                        m["window_index"], m["presence_score"], m["motion_score"],
                        m["audio_score"], m["head_pose_score"], m["composite_score"],
                        m["participant_count"], m["audio_activity_seconds"],
                        m["silence_seconds"], m["missing_data"], m["confidence"],
                    ),
                )

        recs = pipeline_output["recommendations"]
        with db_session() as conn:
            for r in recs:
                conn.execute(
                    """INSERT OR REPLACE INTO recommendations
                       (id,session_id,title,observation,evidence,suggestion,
                        confidence,time_range,source,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        r["id"], r["session_id"], r["title"], r["observation"],
                        r["evidence"], r["suggestion"], r["confidence"],
                        r["time_range"], r["source"], r["created_at"],
                    ),
                )

        # 6. Update session record
        v_res = pipeline_output["video_result"]
        with db_session() as conn:
            conn.execute(
                """UPDATE sessions SET status='completed', ended_at=?,
                   total_frames=?, fps=?, duration_seconds=? WHERE id=?""",
                (
                    datetime.utcnow().isoformat(),
                    v_res.total_frames, round(v_res.fps, 2),
                    round(v_res.duration_seconds, 2), session_id,
                ),
            )

        _progress[session_id] = {"pct": 100, "status": "completed", "error": None}
        logger.info("Processing complete for session %s", session_id)

    except Exception as e:
        logger.exception("Processing failed for session %s", session_id)
        _progress[session_id] = {"pct": 0, "status": "error", "error": str(e)}
        _set_session_error(session_id, str(e))


def _set_session_error(session_id: str, error: str):
    with db_session() as conn:
        conn.execute(
            "UPDATE sessions SET status='error', notes=? WHERE id=?",
            (error[:500], session_id),
        )


def _audit(conn, action, entity_type, entity_id, actor="system"):
    conn.execute(
        """INSERT INTO audit_logs (id, action, entity_type, entity_id, actor, timestamp)
           VALUES (?,?,?,?,?,?)""",
        (uuid.uuid4().hex, action, entity_type, entity_id, actor,
         datetime.utcnow().isoformat()),
    )
