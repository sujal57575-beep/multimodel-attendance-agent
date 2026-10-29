"""
routes/engagement_routes.py
"""

from flask import Blueprint, jsonify
from models.database import db_session, rows_to_list
from utils.metrics import aggregate_windows

bp = Blueprint("engagement", __name__, url_prefix="/api/sessions")


@bp.route("/<session_id>/engagement", methods=["GET"])
def get_engagement(session_id: str):
    with db_session() as conn:
        rows = conn.execute(
            """SELECT * FROM engagement_metrics
               WHERE session_id=? ORDER BY window_index""",
            (session_id,),
        ).fetchall()
    metrics = rows_to_list(rows)
    summary = aggregate_windows(metrics)
    return jsonify({
        "session_id": session_id,
        "windows": metrics,
        "summary": summary,
    }), 200
