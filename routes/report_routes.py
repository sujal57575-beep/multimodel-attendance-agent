"""
routes/report_routes.py
CSV and (future) PDF export.
"""

import io
from flask import Blueprint, jsonify, make_response
from models.database import db_session, row_to_dict, rows_to_list
from utils.report_utils import generate_csv, report_filename

bp = Blueprint("reports", __name__, url_prefix="/api/sessions")


@bp.route("/<session_id>/report", methods=["GET"])
def download_report(session_id: str):
    with db_session() as conn:
        session = row_to_dict(
            conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        )
        participants = rows_to_list(
            conn.execute(
                "SELECT * FROM participants WHERE session_id=?", (session_id,)
            ).fetchall()
        )
        metrics = rows_to_list(
            conn.execute(
                "SELECT * FROM engagement_metrics WHERE session_id=? ORDER BY window_index",
                (session_id,),
            ).fetchall()
        )

    if not session:
        return jsonify({"error": "Session not found"}), 404

    csv_content = generate_csv(session, participants, metrics)
    fname = report_filename(session_id)
    resp = make_response(csv_content)
    resp.headers["Content-Type"] = "text/csv"
    resp.headers["Content-Disposition"] = f"attachment; filename={fname}"
    return resp


@bp.route("/health", methods=["GET"])
def health():
    """System health check."""
    import platform, sys
    from services.face_detector import FaceDetector
    face_det = FaceDetector()

    checks = {
        "python": sys.version.split()[0],
        "platform": platform.system(),
        "opencv": _check_import("cv2"),
        "face_detector_yunet": "available" if face_det.is_available else "fallback",
        "ultralytics": _check_import("ultralytics"),
        "librosa": _check_import("librosa"),
        "pyttsx3": _check_import("pyttsx3"),
        "gemini": _check_import("google.generativeai"),
    }
    return jsonify({"status": "ok", "checks": checks}), 200


def _check_import(module: str) -> str:
    try:
        __import__(module)
        return "available"
    except ImportError:
        return "not installed"
