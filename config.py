"""
config.py — Application Configuration
Multimodal Attendance & Engagement Agent
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # ── Flask ──────────────────────────────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_PATH = os.getenv(
        "DATABASE_PATH", str(BASE_DIR / "storage" / "attendance.db")
    )

    # ── Storage Directories ────────────────────────────────────────────────
    UPLOAD_FOLDER = str(BASE_DIR / "storage" / "uploads")
    PROCESSED_FOLDER = str(BASE_DIR / "storage" / "processed")
    REPORTS_FOLDER = str(BASE_DIR / "storage" / "reports")
    GENERATED_AUDIO_FOLDER = str(BASE_DIR / "storage" / "generated_audio")
    GENERATED_CODE_FOLDER = str(BASE_DIR / "storage" / "generated_code")

    # ── Upload limits ──────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "500")) * 1024 * 1024
    ALLOWED_VIDEO_EXTENSIONS = {"mp4", "avi", "mov", "mkv", "webm"}
    ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "ogg", "m4a", "flac"}

    # ── Computer Vision ────────────────────────────────────────────────────
    CV_BACKEND = os.getenv("CV_BACKEND", "yolov8")   # yolov8 | haar | hog
    YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")
    FRAME_SAMPLE_RATE = int(os.getenv("FRAME_SAMPLE_RATE", "5"))   # every N frames
    ATTENDANCE_THRESHOLD_SECONDS = int(
        os.getenv("ATTENDANCE_THRESHOLD_SECONDS", "120")
    )
    DETECTION_CONFIDENCE = float(os.getenv("DETECTION_CONFIDENCE", "0.45"))

    # ── Engagement ─────────────────────────────────────────────────────────
    ENGAGEMENT_WINDOW_SECONDS = int(os.getenv("ENGAGEMENT_WINDOW_SECONDS", "60"))

    # Weights must sum ≤ 1.0
    ENGAGEMENT_WEIGHTS = {
        "presence": float(os.getenv("EW_PRESENCE", "0.35")),
        "motion": float(os.getenv("EW_MOTION", "0.25")),
        "audio_activity": float(os.getenv("EW_AUDIO", "0.25")),
        "head_pose": float(os.getenv("EW_HEAD_POSE", "0.15")),
    }

    # ── AI / GenAI ─────────────────────────────────────────────────────────
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_ENABLED = bool(os.getenv("GEMINI_API_KEY", ""))

    # ── TTS ────────────────────────────────────────────────────────────────
    TTS_ENABLED = os.getenv("TTS_ENABLED", "true").lower() == "true"
    TTS_ENGINE = os.getenv("TTS_ENGINE", "pyttsx3")   # pyttsx3 | espeak

    # ── Code Execution ─────────────────────────────────────────────────────
    CODE_EXEC_ENABLED = os.getenv("CODE_EXEC_ENABLED", "false").lower() == "true"
    CODE_EXEC_TIMEOUT = int(os.getenv("CODE_EXEC_TIMEOUT", "10"))

    # ── Privacy / Retention ────────────────────────────────────────────────
    DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "90"))
    FACIAL_RECOGNITION_ENABLED = (
        os.getenv("FACIAL_RECOGNITION_ENABLED", "false").lower() == "true"
    )

    # ── Auth ───────────────────────────────────────────────────────────────
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme123")

    # ── Logging ────────────────────────────────────────────────────────────
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = str(BASE_DIR / "storage" / "app.log")

    @staticmethod
    def ensure_dirs():
        """Create all storage directories if they don't exist."""
        dirs = [
            Config.UPLOAD_FOLDER,
            Config.PROCESSED_FOLDER,
            Config.REPORTS_FOLDER,
            Config.GENERATED_AUDIO_FOLDER,
            Config.GENERATED_CODE_FOLDER,
            str(BASE_DIR / "storage"),
        ]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)
