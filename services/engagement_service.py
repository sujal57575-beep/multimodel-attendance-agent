"""
services/engagement_service.py
Merges visual and audio signals into per-window engagement metrics.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from config import Config
from utils.metrics import weighted_sum, normalize, moving_average, aggregate_windows

logger = logging.getLogger(__name__)


class EngagementService:

    def compute(
        self,
        session_id: str,
        video_windows: list[dict],
        audio_windows: list[dict],
        fps: float,
        session_start: datetime,
    ) -> list[dict]:
        """
        Merge video and audio windows → list of engagement metric records
        ready for DB insertion.
        """
        weights = Config.ENGAGEMENT_WEIGHTS
        audio_by_idx = {w["window_index"]: w for w in audio_windows}
        metrics = []

        for vw in video_windows:
            idx = vw["window_index"]
            aw = audio_by_idx.get(idx, {})

            signals = {
                "presence": vw.get("presence_score", 0.0),
                "motion": vw.get("motion_score", 0.0),
                "audio_activity": aw.get("audio_score", 0.0),
                "head_pose": vw.get("head_pose_score", vw.get("presence_score", 0) * 0.8),
            }

            missing = []
            if not aw:
                missing.append("audio")
            if vw.get("presence_score", 0) == 0 and vw.get("max_participant_count", 0) == 0:
                missing.append("visual")

            composite = weighted_sum(signals, weights)
            confidence = 1.0 if not missing else 0.65

            # Wall-clock timestamps
            w_start_sec = vw.get("window_start_seconds", idx * Config.ENGAGEMENT_WINDOW_SECONDS)
            w_end_sec = vw.get("window_end_seconds", w_start_sec + Config.ENGAGEMENT_WINDOW_SECONDS)

            window_start_dt = _offset_dt(session_start, w_start_sec)
            window_end_dt = _offset_dt(session_start, w_end_sec)

            metrics.append({
                "id": uuid.uuid4().hex,
                "session_id": session_id,
                "window_start": window_start_dt.isoformat(),
                "window_end": window_end_dt.isoformat(),
                "window_index": idx,
                "presence_score": round(signals["presence"], 4),
                "motion_score": round(signals["motion"], 4),
                "audio_score": round(signals["audio_activity"], 4),
                "head_pose_score": round(signals["head_pose"], 4),
                "composite_score": round(composite, 4),
                "participant_count": vw.get("max_participant_count", 0),
                "audio_activity_seconds": aw.get("speech_seconds", 0.0),
                "silence_seconds": aw.get("silence_seconds", 0.0),
                "missing_data": json.dumps(missing),
                "confidence": confidence,
            })

        # Apply smoothing to composite scores
        if len(metrics) > 2:
            raw = [m["composite_score"] for m in metrics]
            smoothed = moving_average(raw, window=3)
            for m, s in zip(metrics, smoothed):
                m["composite_score"] = round(s, 4)

        return metrics

    def summarise(self, metrics: list[dict]) -> dict:
        return aggregate_windows(metrics)


def _offset_dt(base: datetime, seconds: float) -> datetime:
    from datetime import timedelta
    return base + timedelta(seconds=seconds)
