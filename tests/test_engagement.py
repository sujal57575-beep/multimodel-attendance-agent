"""
tests/test_engagement.py — Engagement service unit tests
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATABASE_PATH"] = ":memory:"

import unittest
from datetime import datetime
from services.engagement_service import EngagementService


class EngagementServiceTest(unittest.TestCase):

    def setUp(self):
        self.svc = EngagementService()
        self.session_start = datetime(2025, 1, 15, 9, 0, 0)

    def test_compute_basic(self):
        video_windows = [
            {"window_index": 0, "window_start_seconds": 0, "window_end_seconds": 60,
             "presence_score": 0.8, "motion_score": 0.4, "max_participant_count": 10},
            {"window_index": 1, "window_start_seconds": 60, "window_end_seconds": 120,
             "presence_score": 0.6, "motion_score": 0.3, "max_participant_count": 8},
        ]
        audio_windows = [
            {"window_index": 0, "audio_score": 0.7, "speech_seconds": 40, "silence_seconds": 20},
            {"window_index": 1, "audio_score": 0.5, "speech_seconds": 30, "silence_seconds": 30},
        ]
        metrics = self.svc.compute("sid", video_windows, audio_windows, 25.0, self.session_start)
        self.assertEqual(len(metrics), 2)
        for m in metrics:
            self.assertIn("composite_score", m)
            self.assertGreaterEqual(m["composite_score"], 0)
            self.assertLessEqual(m["composite_score"], 1)

    def test_compute_no_audio(self):
        video_windows = [
            {"window_index": 0, "window_start_seconds": 0, "window_end_seconds": 60,
             "presence_score": 0.7, "motion_score": 0.3, "max_participant_count": 5},
        ]
        metrics = self.svc.compute("sid", video_windows, [], 25.0, self.session_start)
        self.assertEqual(len(metrics), 1)
        import json
        missing = json.loads(metrics[0]["missing_data"])
        self.assertIn("audio", missing)

    def test_summarise(self):
        metrics = [
            {"composite_score": 0.4},
            {"composite_score": 0.6},
            {"composite_score": 0.8},
        ]
        summary = self.svc.summarise(metrics)
        self.assertIn("mean", summary)
        self.assertIn("trend", summary)
        self.assertEqual(summary["trend"], "improving")
        self.assertAlmostEqual(summary["mean"], (0.4 + 0.6 + 0.8) / 3, places=3)

    def test_compute_empty(self):
        metrics = self.svc.compute("sid", [], [], 25.0, self.session_start)
        self.assertEqual(metrics, [])


if __name__ == "__main__":
    unittest.main()
