"""
tests/test_face_detector.py — Unit tests for face detection and attendance verification
"""

import os
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from services.face_detector import FaceDetector, FaceDetection
from app import create_app


class FaceDetectorTest(unittest.TestCase):

    def setUp(self):
        self.detector = FaceDetector()

    def test_detector_initialization(self):
        # Should initialize without crashing
        self.assertIsNotNone(self.detector)

    def test_detect_blank_frame(self):
        # 300x300 blank frame should not crash and return a list
        frame = np.zeros((300, 300, 3), dtype=np.uint8)
        faces = self.detector.detect(frame)
        self.assertIsInstance(faces, list)

    def test_detect_none_frame(self):
        faces = self.detector.detect(None)
        self.assertEqual(faces, [])

    def test_match_face_to_person_inside(self):
        # Person bbox at (100, 100, 100, 250) -> upper 45% is y: 100 to ~212
        person_bbox = (100, 100, 100, 250)
        face_bbox = (120, 110, 60, 60) # inside head region
        self.assertTrue(FaceDetector.match_face_to_person(face_bbox, person_bbox))

    def test_match_face_to_person_outside(self):
        # Face is down near the feet/floor
        person_bbox = (100, 100, 100, 250)
        face_bbox = (120, 280, 60, 60)
        self.assertFalse(FaceDetector.match_face_to_person(face_bbox, person_bbox))

    def test_estimate_frontal_symmetric(self):
        # Eye midpoint is x=50, nose is at x=50 -> frontal
        re = (30, 40)
        le = (70, 40)
        nt = (50, 55)
        is_frontal, gaze = self.detector._estimate_frontal(re, le, nt, 60)
        self.assertTrue(is_frontal)
        self.assertGreaterEqual(gaze, 0.7)

    def test_estimate_frontal_turned(self):
        # Eye midpoint is x=50, nose is at x=20 (turned profile)
        re = (30, 40)
        le = (70, 40)
        nt = (15, 55)
        is_frontal, gaze = self.detector._estimate_frontal(re, le, nt, 60)
        self.assertFalse(is_frontal)
        self.assertLess(gaze, 0.6)


class LiveFaceRouteTest(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app.testing = True

    def test_detect_face_no_image(self):
        r = self.client.post("/api/sessions/demo/detect-face", json={})
        self.assertEqual(r.status_code, 400)

    def test_detect_face_valid_base64(self):
        import base64
        import cv2
        dummy = np.zeros((100, 100, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", dummy)
        b64 = base64.b64encode(buf).decode("utf-8")

        r = self.client.post(
            "/api/sessions/demo/detect-face",
            json={"image": f"data:image/jpeg;base64,{b64}"},
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("faces_detected", data)
        self.assertIn("faces", data)
        self.assertIn("detector_backend", data)


if __name__ == "__main__":
    unittest.main()
