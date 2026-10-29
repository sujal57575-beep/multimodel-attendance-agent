"""
utils/report_utils.py — CSV and PDF report generation
"""

import csv
import io
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_csv(session: dict, participants: list, metrics: list) -> str:
    """Return CSV string for a session report."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["=== SESSION REPORT ==="])
    writer.writerow(["Session ID", session.get("id", "")])
    writer.writerow(["Name", session.get("name", "")])
    writer.writerow(["Subject", session.get("subject", "")])
    writer.writerow(["Instructor", session.get("instructor", "")])
    writer.writerow(["Started", session.get("started_at", "")])
    writer.writerow(["Duration (s)", session.get("duration_seconds", "")])
    writer.writerow([])

    writer.writerow(["=== ATTENDANCE ==="])
    writer.writerow(["Track ID", "Display Name", "First Seen", "Last Seen",
                     "Duration (s)", "Attendance Marked", "Needs Review"])
    for p in participants:
        writer.writerow([
            p.get("track_id", ""),
            p.get("display_name", "Anonymous"),
            p.get("first_seen_at", ""),
            p.get("last_seen_at", ""),
            p.get("total_duration_seconds", ""),
            "Yes" if p.get("attendance_marked") else "No",
            "Yes" if p.get("needs_review") else "No",
        ])
    writer.writerow([])

    if metrics:
        writer.writerow(["=== ENGAGEMENT TIMELINE ==="])
        writer.writerow(["Window", "Start", "End", "Presence", "Motion",
                         "Audio", "Head Pose", "Composite", "Participants"])
        for m in metrics:
            writer.writerow([
                m.get("window_index", ""),
                m.get("window_start", ""),
                m.get("window_end", ""),
                m.get("presence_score", ""),
                m.get("motion_score", ""),
                m.get("audio_score", ""),
                m.get("head_pose_score", ""),
                m.get("composite_score", ""),
                m.get("participant_count", ""),
            ])

    return output.getvalue()


def report_filename(session_id: str, fmt: str = "csv") -> str:
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    return f"report_{session_id[:8]}_{ts}.{fmt}"
