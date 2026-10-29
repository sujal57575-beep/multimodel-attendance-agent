"""
routes/recommendation_routes.py
"""

import json
from flask import Blueprint, jsonify
from models.database import db_session, rows_to_list

bp = Blueprint("recommendations", __name__, url_prefix="/api/sessions")


@bp.route("/<session_id>/recommendations", methods=["GET"])
def get_recommendations(session_id: str):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM recommendations WHERE session_id=? ORDER BY confidence DESC",
            (session_id,),
        ).fetchall()
    recs = rows_to_list(rows)
    for r in recs:
        for field in ("evidence", "time_range"):
            try:
                r[field] = json.loads(r[field]) if r.get(field) else {}
            except Exception:
                pass
    return jsonify({"session_id": session_id, "recommendations": recs}), 200
