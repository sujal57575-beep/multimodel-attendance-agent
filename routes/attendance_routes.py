"""
routes/attendance_routes.py
"""

from flask import Blueprint, jsonify, request
from models.database import db_session, rows_to_list
from services.attendance_service import AttendanceService

bp = Blueprint("attendance", __name__, url_prefix="/api/sessions")
att_svc = AttendanceService()


@bp.route("/<session_id>/attendance", methods=["GET"])
def get_attendance(session_id: str):
    records = att_svc.get_attendance(session_id)
    marked = sum(1 for r in records if r.get("attendance_marked"))
    return jsonify({
        "session_id": session_id,
        "participants": records,
        "total": len(records),
        "marked": marked,
        "attendance_pct": round(marked / len(records) * 100, 1) if records else 0,
    }), 200


@bp.route("/<session_id>/attendance/<participant_id>", methods=["PATCH"])
def update_attendance(session_id: str, participant_id: str):
    data = request.get_json(force=True, silent=True) or {}
    success = att_svc.update_participant(participant_id, data)
    if not success:
        return jsonify({"error": "No valid fields or participant not found"}), 400
    return jsonify({"updated": True}), 200
