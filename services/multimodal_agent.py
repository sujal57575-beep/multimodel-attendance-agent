"""
services/multimodal_agent.py
EPIC 4: AI IMPLEMENTATION
  - Activity 4.1: Multimodal Agent Implementation
  - Activity 4.2: Multimodal Signal Fusion
  - Activity 4.3: Engagement Scoring Logic
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional

from config import Config
from services.attendance_service import AttendanceService
from services.audio_processor import AudioProcessor
from services.engagement_service import EngagementService
from services.recommendation_service import RecommendationService
from services.video_processor import ProcessingResult, VideoProcessor

logger = logging.getLogger(__name__)


class MultimodalAttendanceAgent:
    """
    EPIC 4 - Activity 4.1: Multimodal Agent Implementation
    Orchestrates the entire multimodal intelligence pipeline:
      1. Vision Processing: YOLOv8 / HOG + YuNet face detection & tracking (EPIC 2)
      2. Audio Processing: FFmpeg extraction + VAD noise/speech analysis (EPIC 3)
      3. Multimodal Signal Fusion: Weighted merging of visual, motion, face, & speech (Activity 4.2)
      4. Engagement Scoring Logic: Windowed aggregation, smoothing, trend estimation (Activity 4.3)
      5. Analytics & Teaching Recommendations (EPIC 5)
    """

    def __init__(self):
        self.video_processor = VideoProcessor()
        self.audio_processor = AudioProcessor()
        self.engagement_service = EngagementService()
        self.attendance_service = AttendanceService()
        self.recommendation_service = RecommendationService()
        logger.info("MultimodalAttendanceAgent initialized.")

    def run_session_pipeline(
        self,
        session_id: str,
        video_path: str,
        session_start: datetime,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> dict:
        """
        Executes the end-to-end multimodal processing pipeline for a session recording.
        Returns a dictionary containing attendance, engagement, and recommendation results.
        """
        def update_progress(pct: int, msg: str):
            if progress_cb:
                progress_cb(pct, msg)
            logger.info("[%s] %d%% - %s", session_id[:8], pct, msg)

        # ── Step 1: Vision Module (EPIC 2: Activities 2.1 & 2.2) ──────
        update_progress(5, "Running Vision Module: Face Detection & Person Tracking…")
        video_result: ProcessingResult = self.video_processor.process(
            video_path=video_path,
            session_id=session_id,
            progress_cb=lambda p, m: update_progress(5 + int(p * 0.45), m),
        )

        if video_result.error:
            logger.error("Vision processing error: %s", video_result.error)
            raise RuntimeError(video_result.error)

        # Persist Attendance & Face Verification (Activity 2.2)
        marked_count = self.attendance_service.persist_results(video_result, session_start)
        attendance_records = self.attendance_service.get_attendance(session_id)
        attendance_pct = (
            round(marked_count / len(attendance_records) * 100, 1)
            if attendance_records else 0.0
        )

        # ── Step 2: Audio Module (EPIC 3: Activities 3.1 & 3.2) ──────
        update_progress(55, "Running Audio Module: Extracting audio signal…")
        audio_path = self.audio_processor.extract_audio(video_path, Config.UPLOAD_FOLDER)
        audio_result = {"windows": [], "session_summary": {}}

        if audio_path:
            update_progress(65, "Running Audio Module: Speech Activity & Noise Analysis…")
            audio_result = self.audio_processor.analyse_noise_and_speech(
                audio_path,
                window_seconds=Config.ENGAGEMENT_WINDOW_SECONDS,
            )
        else:
            logger.warning("No audio stream found or extraction failed; proceeding with visual-only fusion.")

        # ── Step 3: Multimodal Signal Fusion (Activity 4.2) ───────────
        # ── Step 4: Engagement Scoring Logic (Activity 4.3) ────────────
        update_progress(80, "Fusing Multimodal Signals & Computing Engagement Scoring Logic…")
        engagement_metrics = self.engagement_service.compute(
            session_id=session_id,
            video_windows=video_result.frame_metrics,
            audio_windows=audio_result.get("windows", []),
            fps=video_result.fps,
            session_start=session_start,
        )
        engagement_summary = self.engagement_service.summarise(engagement_metrics)

        # ── Step 5: Analytics & Recommendation Engine (EPIC 5) ────────
        update_progress(92, "Generating AI Teaching Suggestions & Session Analytics…")
        recommendations = self.recommendation_service.generate(
            session_id=session_id,
            engagement_summary=engagement_summary,
            audio_result=audio_result,
            attendance_pct=attendance_pct,
        )

        update_progress(100, "Processing complete.")
        return {
            "session_id": session_id,
            "video_result": video_result,
            "audio_result": audio_result,
            "audio_path": audio_path,
            "attendance_marked": marked_count,
            "attendance_pct": attendance_pct,
            "engagement_metrics": engagement_metrics,
            "engagement_summary": engagement_summary,
            "recommendations": recommendations,
        }
