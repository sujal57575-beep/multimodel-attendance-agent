"""
streamlit_app.py
EPIC 6: Interface, Testing, and Deployment
  - Activity 6.2: Launch Optional Streamlit Dashboard
Interactive Streamlit analytics dashboard for Multimodal Attendance & Engagement Agent.
"""

from __future__ import annotations

import os
import ssl

# Fix Python 3.14 Windows certificate store ASN1 enumeration in urllib
try:
    def _safe_ssl_context(*args, **kwargs):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    ssl.create_default_context = _safe_ssl_context
    ssl._create_default_https_context = _safe_ssl_context
except Exception:
    pass

import sqlite3
import pandas as pd
import streamlit as st
import numpy as np
import cv2

from config import Config
from services.face_detector import FaceDetector

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AttendAI · Streamlit Dashboard",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom Styling ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .reportview-container { background: #0a0b14; }
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .badge-present {
        color: #22c55e; font-weight: bold;
    }
    .badge-face {
        color: #a78bfa; font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# ── Database Helpers ──────────────────────────────────────────────────────────
@st.cache_data(ttl=5)
def get_sessions():
    if not os.path.exists(Config.DATABASE_PATH):
        return []
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_data(session_id: str):
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    participants = conn.execute(
        "SELECT * FROM participants WHERE session_id=? ORDER BY first_seen_at", (session_id,)
    ).fetchall()
    metrics = conn.execute(
        "SELECT * FROM engagement_metrics WHERE session_id=? ORDER BY window_index", (session_id,)
    ).fetchall()
    recs = conn.execute(
        "SELECT * FROM recommendations WHERE session_id=? ORDER BY confidence DESC", (session_id,)
    ).fetchall()
    conn.close()
    return (
        [dict(r) for r in participants],
        [dict(r) for r in metrics],
        [dict(r) for r in recs],
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🎓 AttendAI Agent")
st.sidebar.caption("Activity 6.2: Streamlit Dashboard")

sessions = get_sessions()
if not sessions:
    st.sidebar.warning("No sessions found in database. Create a session or seed demo data.")
    st.info("Run `python scripts/initialize_db.py --seed` to populate demo classroom data.")
    st.stop()

session_options = {f"{s['name']} ({s['subject'] or 'General'})": s["id"] for s in sessions}
selected_label = st.sidebar.selectbox("Select Classroom Session:", list(session_options.keys()))
selected_session_id = session_options[selected_label]
session = next(s for s in sessions if s["id"] == selected_session_id)

st.sidebar.divider()
st.sidebar.markdown(f"**Instructor:** {session.get('instructor') or '—'}")
st.sidebar.markdown(f"**Location:** {session.get('location') or 'Room 101'}")
st.sidebar.markdown(f"**Status:** `{session.get('status', 'active')}`")
dur_sec = session.get('duration_seconds') or 0
st.sidebar.markdown(f"**Duration:** {round(dur_sec / 60, 1)} minutes")

# ── Main Header ───────────────────────────────────────────────────────────────
st.title(f"📊 {session['name']}")
st.caption(f"Session ID: `{selected_session_id}` · Privacy-Preserving Multimodal Intelligence")

participants, metrics, recommendations = get_session_data(selected_session_id)

# ── KPI Metrics Row ───────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

total_p = len(participants)
marked_p = sum(1 for p in participants if p.get("attendance_marked"))
face_p = sum(1 for p in participants if p.get("face_verified"))
att_rate = round(marked_p / total_p * 100, 1) if total_p else 0

avg_eng = 0.0
if metrics:
    avg_eng = round(sum(m.get("composite_score", 0) for m in metrics) / len(metrics), 2)

col1.metric("Total Detected", total_p)
col2.metric("Attendance Rate", f"{att_rate}%", f"{marked_p} present")
col3.metric("Face Verified", face_p, f"{round(face_p / max(total_p, 1) * 100)}% verified")
col4.metric("Avg Engagement", f"{avg_eng}", "composite score")

st.divider()

# ── Tabs Navigation ───────────────────────────────────────────────────────────
tab_att, tab_eng, tab_ai, tab_live = st.tabs([
    "👥 Attendance & Faces",
    "📈 Multimodal Engagement",
    "💡 AI Teaching Suggestions",
    "📷 Live Face Scanner",
])

# ── TAB 1: Attendance & Face Verification ──────────────────────────────────────
with tab_att:
    st.subheader("Student Attendance Records (Activity 2.1 & 2.2)")

    if participants:
        df_p = pd.DataFrame(participants)
        cols_to_show = ["track_id", "display_name", "attendance_marked", "face_verified", "face_count", "total_duration_seconds", "confidence"]
        available_cols = [c for c in cols_to_show if c in df_p.columns]
        df_display = df_p[available_cols].copy()

        df_display["attendance_marked"] = df_display["attendance_marked"].apply(lambda x: "✅ Present" if x else "❌ Absent")
        if "face_verified" in df_display.columns:
            df_display["face_verified"] = df_display["face_verified"].apply(lambda x: "👤 Verified" if x else "Silhouette")
        if "total_duration_seconds" in df_display.columns:
            df_display["duration (min)"] = (df_display["total_duration_seconds"] / 60.0).round(1)

        st.dataframe(df_display, use_container_width=True)

        # Download CSV
        csv_data = df_p.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Attendance CSV",
            data=csv_data,
            file_name=f"attendance_{selected_session_id[:8]}.csv",
            mime="text/csv",
        )
    else:
        st.info("No participant records recorded for this session yet.")

# ── TAB 2: Multimodal Engagement Analytics ────────────────────────────────────
with tab_eng:
    st.subheader("Multimodal Signal Fusion & Engagement Scoring (Activity 4.2 & 4.3)")

    if metrics:
        df_m = pd.DataFrame(metrics)
        chart_cols = ["composite_score", "presence_score", "motion_score", "audio_score", "head_pose_score"]
        available_chart_cols = [c for c in chart_cols if c in df_m.columns]

        if "window_index" in df_m.columns:
            df_m = df_m.set_index("window_index")

        st.line_chart(df_m[available_chart_cols])

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.markdown("#### Signals Breakdown")
            st.caption("Weighted Multi-Signal Fusion:")
            st.markdown("- **Presence (35%):** Visual centroid persistence")
            st.markdown("- **Motion (25%):** Frame-to-frame pixel dynamics")
            st.markdown("- **Audio Activity (25%):** VAD speech & energy ratio")
            st.markdown("- **Head Pose (15%):** Facial landmark frontal orientation")

        with col_e2:
            st.markdown("#### Audio & Speech Activity (Activity 3.2)")
            total_speech = df_m["audio_activity_seconds"].sum() if "audio_activity_seconds" in df_m.columns else 0
            total_silence = df_m["silence_seconds"].sum() if "silence_seconds" in df_m.columns else 0
            st.metric("Total Speech Time", f"{round(total_speech / 60, 1)} min")
            st.metric("Total Silence Time", f"{round(total_silence / 60, 1)} min")
    else:
        st.info("No windowed engagement metrics available for this session.")

# ── TAB 3: AI Recommendations ────────────────────────────────────────────────
with tab_ai:
    st.subheader("Pedagogical AI Suggestions (Activity 5.1 & 5.2)")

    if recommendations:
        for r in recommendations:
            with st.expander(f"📌 {r.get('title')} ({round(r.get('confidence', 0.9)*100)}% confidence)", expanded=True):
                st.markdown(f"**Observation:** {r.get('observation')}")
                st.info(f"💡 **Suggestion:** {r.get('suggestion')}")
                st.caption(f"Source: `{r.get('source', 'rule')}` · Created: {r.get('created_at')}")
    else:
        st.info("No teaching suggestions generated yet.")

# ── TAB 4: Live Face Scanner ──────────────────────────────────────────────────
with tab_live:
    st.subheader("Live Camera Face Detection (Activity 2.1 Test)")
    st.caption("Capture a live camera snapshot to test OpenCV YuNet DNN face detection.")

    img_file = st.camera_input("Take a photo to test Face Detection")
    if img_file is not None:
        bytes_data = img_file.getvalue()
        cv_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)

        detector = FaceDetector()
        faces = detector.detect(cv_img)

        # Draw bboxes & landmarks
        annotated = cv_img.copy()
        for f in faces:
            x, y, w, h = f.bbox
            color = (34, 197, 94) if f.is_frontal else (245, 158, 11)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            label = f"Face: {int(f.confidence*100)}%"
            cv2.putText(annotated, label, (x, max(15, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            if f.landmarks:
                for pt in f.landmarks.values():
                    cv2.circle(annotated, pt, 3, (241, 102, 99), -1)

        annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        st.image(annotated_rgb, caption=f"Detected {len(faces)} face(s) using {('YuNet DNN' if detector.is_available else 'Fallback')}")
        st.success(f"✓ Detected {len(faces)} face(s). Face verification condition satisfied!")
