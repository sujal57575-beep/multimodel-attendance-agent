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
    face_verified_count = sum(1 for r in records if r.get("face_verified"))
    return jsonify({
        "session_id": session_id,
        "participants": records,
        "total": len(records),
        "marked": marked,
        "face_verified_count": face_verified_count,
        "attendance_pct": round(marked / len(records) * 100, 1) if records else 0,
    }), 200


@bp.route("/<session_id>/attendance/<participant_id>", methods=["PATCH"])
def update_attendance(session_id: str, participant_id: str):
    data = request.get_json(force=True, silent=True) or {}
    success = att_svc.update_participant(participant_id, data)
    if not success:
        return jsonify({"error": "No valid fields or participant not found"}), 400
    return jsonify({"updated": True}), 200


@bp.route("/<session_id>/detect-face", methods=["POST"])
def detect_live_face(session_id: str):
    """
    Real-time face detection endpoint for webcam frames.
    Accepts base64 or raw image, runs FaceDetector, returns detected faces with bboxes.
    """
    import base64
    import numpy as np
    import cv2
    from services.face_detector import FaceDetector

    data = request.get_json(force=True, silent=True) or {}
    image_b64 = data.get("image")
    if not image_b64:
        return jsonify({"error": "No image data provided"}), 400

    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    try:
        img_bytes = base64.b64decode(image_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({"error": "Failed to decode frame"}), 400

        detector = FaceDetector()
        faces = detector.detect(frame)
        face_list = [
            {
                "bbox": f.bbox,
                "confidence": f.confidence,
                "is_frontal": f.is_frontal,
                "gaze_score": f.gaze_score,
                "landmarks": f.landmarks,
            }
            for f in faces
        ]

        return jsonify({
            "faces_detected": len(face_list),
            "faces": face_list,
            "detector_backend": "YuNet (DNN)" if detector.is_available else "Fallback",
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
