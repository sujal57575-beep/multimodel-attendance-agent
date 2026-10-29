"""
services/face_detector.py
OpenCV YuNet DNN face detection and landmark analysis for attendance verification.
Falls back to upper-body face heuristic if ONNX model is unavailable.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class FaceDetection:
    bbox: tuple[int, int, int, int]    # (x, y, w, h)
    confidence: float
    landmarks: dict[str, tuple[int, int]] = field(default_factory=dict)
    is_frontal: bool = True            # whether the face is oriented towards camera
    gaze_score: float = 1.0            # 0.0 - 1.0 attentiveness estimate


class FaceDetector:
    """
    High-performance, offline face detector utilizing OpenCV's YuNet ONNX model.
    Detects faces, computes attentiveness/frontal orientation, and validates presence.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or Config.FACE_MODEL_PATH
        self.detector = None
        self._input_size = (320, 320)
        self._init_detector()

    def _init_detector(self):
        if not Config.FACE_DETECTION_ENABLED:
            logger.info("Face detection is disabled in config.")
            return

        if not os.path.exists(self.model_path):
            # Look in storage/ or current dir
            alt_path = os.path.join(Config.BASE_DIR, "storage", "face_detection_yunet_2023mar.onnx")
            if os.path.exists(alt_path):
                self.model_path = alt_path

        if os.path.exists(self.model_path) and os.path.getsize(self.model_path) > 1000:
            try:
                self.detector = cv2.FaceDetectorYN_create(
                    self.model_path,
                    "",
                    self._input_size,
                    Config.FACE_DETECTION_CONFIDENCE,
                    0.3,   # NMS threshold
                    5000,  # top_k
                )
                logger.info("YuNet face detector initialized from %s", self.model_path)
            except Exception as e:
                logger.warning("Failed to initialize FaceDetectorYN (%s); using fallback.", e)
                self.detector = None
        else:
            logger.warning("Face model not found at %s; using skin/contour fallback.", self.model_path)
            self.detector = None

    @property
    def is_available(self) -> bool:
        return self.detector is not None

    def detect(self, frame: np.ndarray) -> list[FaceDetection]:
        """
        Detect faces in a full BGR frame.
        Returns a list of FaceDetection objects with bboxes and landmark metrics.
        """
        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]

        if self.detector is not None:
            return self._detect_yunet(frame, w, h)
        return self._detect_fallback(frame, w, h)

    def _detect_yunet(self, frame: np.ndarray, w: int, h: int) -> list[FaceDetection]:
        try:
            # Set dynamic frame size for YuNet
            if self._input_size != (w, h):
                self._input_size = (w, h)
                self.detector.setInputSize((w, h))

            _, faces = self.detector.detect(frame)
            if faces is None or len(faces) == 0:
                return []

            results = []
            for face in faces:
                fx = max(0, int(face[0]))
                fy = max(0, int(face[1]))
                fw = min(w - fx, int(face[2]))
                fh = min(h - fy, int(face[3]))
                conf = float(face[14])

                if conf < Config.FACE_DETECTION_CONFIDENCE:
                    continue

                # Landmarks: 5 points (re, le, nt, rmc, lmc)
                re = (int(face[4]), int(face[5]))
                le = (int(face[6]), int(face[7]))
                nt = (int(face[8]), int(face[9]))
                rmc = (int(face[10]), int(face[11]))
                lmc = (int(face[12]), int(face[13]))

                landmarks = {
                    "right_eye": re,
                    "left_eye": le,
                    "nose_tip": nt,
                    "right_mouth": rmc,
                    "left_mouth": lmc,
                }

                # Evaluate frontal orientation
                is_frontal, gaze = self._estimate_frontal(re, le, nt, fw)

                results.append(
                    FaceDetection(
                        bbox=(fx, fy, fw, fh),
                        confidence=round(conf, 4),
                        landmarks=landmarks,
                        is_frontal=is_frontal,
                        gaze_score=round(gaze, 3),
                    )
                )
            return results
        except Exception as e:
            logger.error("YuNet detection error: %s", e)
            return self._detect_fallback(frame, w, h)

    def _estimate_frontal(
        self,
        re: tuple[int, int],
        le: tuple[int, int],
        nt: tuple[int, int],
        face_width: int,
    ) -> tuple[bool, float]:
        """
        Determines if a detected face is frontal vs turned away
        by checking the horizontal position of nose relative to the two eyes.
        """
        eye_dist = abs(le[0] - re[0])
        if eye_dist <= 2 or face_width <= 2:
            return True, 0.7

        # Horizontal midpoint between eyes
        mid_x = (re[0] + le[0]) / 2.0
        # Horizontal offset of nose from midpoint
        offset = abs(nt[0] - mid_x)
        ratio = offset / eye_dist

        # If nose is within 35% of midpoint between eyes, face is facing front
        is_frontal = ratio < 0.35
        gaze_score = max(0.2, min(1.0, 1.0 - (ratio * 1.5)))
        return is_frontal, gaze_score

    def _detect_fallback(self, frame: np.ndarray, w: int, h: int) -> list[FaceDetection]:
        """
        Lightweight fallback face heuristic using skin-color segmentation and contour geometry.
        Used if ONNX runtime is absent.
        """
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            # Skin tone range in HSV
            lower = np.array([0, 28, 60], dtype=np.uint8)
            upper = np.array([22, 175, 255], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower, upper)

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            detections = []
            min_area = (w * h) * 0.003
            max_area = (w * h) * 0.25

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if min_area <= area <= max_area:
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    aspect = bh / max(bw, 1)
                    # Faces generally have aspect ratio 1.1 - 1.6
                    if 0.9 <= aspect <= 1.8:
                        detections.append(
                            FaceDetection(
                                bbox=(x, y, bw, bh),
                                confidence=0.55,
                                is_frontal=True,
                                gaze_score=0.7,
                            )
                        )
            return detections
        except Exception as e:
            logger.debug("Fallback face detect error: %s", e)
            return []

    @staticmethod
    def match_face_to_person(
        face_bbox: tuple[int, int, int, int],
        person_bbox: tuple[int, int, int, int],
    ) -> bool:
        """
        Check if a detected face belongs to a tracked person bounding box.
        A face typically sits within the upper 45% of the person's bounding box.
        """
        fx, fy, fw, fh = face_bbox
        px, py, pw, ph = person_bbox

        fcx = fx + fw // 2
        fcy = fy + fh // 2

        # Person head region (horizontal full width + margin, vertical top 45%)
        margin_x = pw * 0.2
        in_x = (px - margin_x) <= fcx <= (px + pw + margin_x)
        in_y = (py - ph * 0.1) <= fcy <= (py + ph * 0.5)

        return in_x and in_y
