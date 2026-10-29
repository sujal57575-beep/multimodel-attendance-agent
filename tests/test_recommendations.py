"""
tests/test_recommendations.py — Recommendation engine tests
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["GEMINI_API_KEY"] = ""   # disable Gemini for tests

import unittest
from services.recommendation_service import RecommendationService


class RecommendationTest(unittest.TestCase):

    def setUp(self):
        self.svc = RecommendationService()

    def test_low_engagement_rule(self):
        summary = {
            "mean": 0.28, "trend": "declining",
            "low_engagement_windows": 5, "window_count": 8, "min": 0.15, "max": 0.5,
        }
        audio = {"windows": [{"audio_score": 0.3}], "session_summary": {"speech_dominant_windows": 2}}
        recs = self.svc.generate("test-sid", summary, audio, 70.0)
        titles = [r["title"] for r in recs]
        self.assertTrue(any("Engagement" in t for t in titles))

    def test_low_attendance_rule(self):
        summary = {"mean": 0.6, "trend": "stable", "low_engagement_windows": 0, "window_count": 5}
        audio = {"windows": [], "session_summary": {}}
        recs = self.svc.generate("test-sid", summary, audio, 45.0)
        titles = [r["title"] for r in recs]
        self.assertTrue(any("Attendance" in t for t in titles))

    def test_no_data_fallback(self):
        summary = {"mean": 0.5, "trend": "stable", "low_engagement_windows": 0, "window_count": 0}
        audio = {"windows": [], "session_summary": {}}
        recs = self.svc.generate("test-sid", summary, audio, 80.0)
        self.assertTrue(len(recs) > 0)
        for r in recs:
            self.assertIn("id", r)
            self.assertIn("title", r)
            self.assertIn("suggestion", r)
            self.assertIn("confidence", r)

    def test_recommendation_structure(self):
        summary = {"mean": 0.4, "trend": "declining", "low_engagement_windows": 4, "window_count": 6}
        audio = {"windows": [{"audio_score": 0.2}] * 5, "session_summary": {"speech_dominant_windows": 4}}
        recs = self.svc.generate("test-sid", summary, audio, 75.0)
        for r in recs:
            self.assertIn("session_id", r)
            self.assertIn("evidence", r)
            self.assertIn("time_range", r)
            self.assertIn("source", r)
            self.assertGreaterEqual(r["confidence"], 0)
            self.assertLessEqual(r["confidence"], 1)


if __name__ == "__main__":
    unittest.main()
