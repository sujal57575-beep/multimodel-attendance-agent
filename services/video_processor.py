"""
services/video_processor.py
YOLOv8-based participant detection, tracking, and attendance marking.
Falls back to OpenCV HOG if YOLOv8 is unavailable.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from config import Config

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TrackedParticipant:
    track_id: str
    first_frame: int
    last_frame: int
    first_time: float          # seconds from video start
    last_time: float
    frame_appearances: int = 0
    bbox_history: list = field(default_factory=list)
    attendance_marked: bool = False
    confidence_sum: float = 0.0
    confidence_count: int = 0

    @property
    def avg_confidence(self) -> float:
        if self.confidence_count == 0:
            return 0.0
        return self.confidence_sum / self.confidence_count

    @property
    def total_duration(self) -> float:
        return self.last_time - self.first_time


@dataclass
class ProcessingResult:
    session_id: str
    total_frames: int
    processed_frames: int
    fps: float
    duration_seconds: float
    participants: list[TrackedParticipant]
    frame_metrics: list[dict]          # per-window engagement signals
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


# ── Detector back-ends ────────────────────────────────────────────────────────

def _load_yolo():
    try:
        from ultralytics import YOLO
        model = YOLO(Config.YOLO_MODEL)
        logger.info("YOLOv8 model loaded: %s", Config.YOLO_MODEL)
        return model
    except Exception as e:
        logger.warning("YOLOv8 unavailable (%s); falling back to HOG", e)
        return None


def _hog_detector():
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    return hog


# ── Main processor ────────────────────────────────────────────────────────────

class VideoProcessor:
    """
    Processes a video file to detect, track, and record participants.
    Emits progress via an optional callback: callback(progress_pct, status_msg)
    """

    def __init__(self):
        self.yolo = _load_yolo()
        self.hog = _hog_detector() if self.yolo is None else None
        self._backend = "yolov8" if self.yolo else "hog"
        logger.info("VideoProcessor backend: %s", self._backend)

    # ── Public API ────────────────────────────────────────────────────────

    def process(
        self,
        video_path: str,
        session_id: str,
        progress_cb=None,
    ) -> ProcessingResult:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return ProcessingResult(
                session_id=session_id,
                total_frames=0, processed_frames=0, fps=0,
                duration_seconds=0, participants=[], frame_metrics=[],
                error=f"Cannot open video: {video_path}",
            )

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        logger.info(
            "Processing %s  frames=%d fps=%.1f dur=%.1fs",
            video_path, total_frames, fps, duration,
        )

        trackers: dict[str, TrackedParticipant] = {}
        frame_metrics: list[dict] = []
        prev_gray = None
        frame_idx = 0
        processed = 0
        sample_rate = max(1, Config.FRAME_SAMPLE_RATE)

        window_seconds = Config.ENGAGEMENT_WINDOW_SECONDS
        window_frames = int(window_seconds * fps)
        current_window: list[dict] = []
        window_index = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            ts = frame_idx / fps
            frame_idx += 1

            if frame_idx % sample_rate != 0:
                continue

            processed += 1
            detections = self._detect(frame)

            # ── motion estimate ───────────────────────────────────────────
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            motion_score = 0.0
            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                motion_score = float(np.mean(diff)) / 255.0
            prev_gray = gray

            # ── update trackers ───────────────────────────────────────────
            seen_ids = set()
            for (x, y, w, h, conf) in detections:
                tid = self._match_or_create(trackers, x, y, w, h, ts)
                p = trackers[tid]
                p.last_frame = frame_idx
                p.last_time = ts
                p.frame_appearances += 1
                p.confidence_sum += conf
                p.confidence_count += 1
                p.bbox_history.append((x, y, w, h))
                seen_ids.add(tid)

            # ── attendance marking ────────────────────────────────────────
            threshold = Config.ATTENDANCE_THRESHOLD_SECONDS
            for p in trackers.values():
                if not p.attendance_marked and p.total_duration >= threshold:
                    p.attendance_marked = True
                    logger.debug("Attendance marked for track %s", p.track_id)

            # ── window metric accumulation ────────────────────────────────
            current_window.append({
                "ts": ts,
                "count": len(detections),
                "motion": motion_score,
            })

            if len(current_window) * sample_rate >= window_frames:
                wm = self._aggregate_window(
                    current_window, window_index, fps
                )
                frame_metrics.append(wm)
                current_window = []
                window_index += 1

            if progress_cb and total_frames > 0:
                pct = int((frame_idx / total_frames) * 100)
                progress_cb(pct, f"Analysing frame {frame_idx}/{total_frames}")

        # flush final window
        if current_window:
            wm = self._aggregate_window(current_window, window_index, fps)
            frame_metrics.append(wm)

        cap.release()

        result = ProcessingResult(
            session_id=session_id,
            total_frames=total_frames,
            processed_frames=processed,
            fps=fps,
            duration_seconds=duration,
            participants=list(trackers.values()),
            frame_metrics=frame_metrics,
        )
        if self._backend == "hog":
            result.warnings.append(
                "YOLOv8 unavailable; HOG person detector used (lower accuracy)."
            )
        logger.info(
            "Processing complete: %d participants, %d windows",
            len(trackers), len(frame_metrics),
        )
        return result

    # ── Detection ─────────────────────────────────────────────────────────

    def _detect(self, frame) -> list[tuple]:
        """Return list of (x, y, w, h, confidence)."""
        if self.yolo:
            return self._yolo_detect(frame)
        return self._hog_detect(frame)

    def _yolo_detect(self, frame) -> list[tuple]:
        try:
            results = self.yolo(frame, classes=[0], verbose=False,
                                conf=Config.DETECTION_CONFIDENCE)
            detections = []
            for r in results:
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    detections.append((x1, y1, x2 - x1, y2 - y1, conf))
            return detections
        except Exception as e:
            logger.error("YOLO detect error: %s", e)
            return []

    def _hog_detect(self, frame) -> list[tuple]:
        try:
            small = cv2.resize(frame, (640, 360))
            scale = frame.shape[1] / 640
            rects, weights = self.hog.detectMultiScale(
                small, winStride=(8, 8), padding=(4, 4), scale=1.05
            )
            detections = []
            for (x, y, w, h), wt in zip(rects, weights):
                conf = min(1.0, float(wt[0]) / 2.0)
                if conf >= Config.DETECTION_CONFIDENCE:
                    detections.append((
                        int(x * scale), int(y * scale),
                        int(w * scale), int(h * scale), conf
                    ))
            return detections
        except Exception as e:
            logger.error("HOG detect error: %s", e)
            return []

    # ── Simple centroid tracker ───────────────────────────────────────────

    def _match_or_create(
        self,
        trackers: dict,
        x: int, y: int, w: int, h: int,
        ts: float,
        iou_threshold: float = 0.3,
    ) -> str:
        cx = x + w // 2
        cy = y + h // 2

        best_id = None
        best_dist = float("inf")
        for tid, p in trackers.items():
            if not p.bbox_history:
                continue
            lx, ly, lw, lh = p.bbox_history[-1]
            lcx = lx + lw // 2
            lcy = ly + lh // 2
            dist = ((cx - lcx) ** 2 + (cy - lcy) ** 2) ** 0.5
            if dist < best_dist and dist < 120:
                best_dist = dist
                best_id = tid

        if best_id:
            return best_id

        new_id = uuid.uuid4().hex[:8]
        trackers[new_id] = TrackedParticipant(
            track_id=new_id,
            first_frame=0,
            last_frame=0,
            first_time=ts,
            last_time=ts,
        )
        return new_id

    # ── Window aggregation ────────────────────────────────────────────────

    @staticmethod
    def _aggregate_window(frames: list[dict], idx: int, fps: float) -> dict:
        if not frames:
            return {}
        counts = [f["count"] for f in frames]
        motions = [f["motion"] for f in frames]
        max_count = max(counts) if counts else 1
        avg_presence = sum(min(c, max_count) for c in counts) / (len(counts) * max(max_count, 1))
        avg_motion = sum(motions) / len(motions) if motions else 0.0

        ts_start = frames[0]["ts"]
        ts_end = frames[-1]["ts"]
        return {
            "window_index": idx,
            "window_start_seconds": ts_start,
            "window_end_seconds": ts_end,
            "avg_participant_count": round(sum(counts) / len(counts), 2),
            "max_participant_count": max(counts),
            "presence_score": round(min(avg_presence, 1.0), 4),
            "motion_score": round(min(avg_motion * 10, 1.0), 4),   # scale up
        }
