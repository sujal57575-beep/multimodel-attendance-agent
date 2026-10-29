"""
tests/test_attendance.py — Attendance logic unit tests
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATABASE_PATH"] = ":memory:"

import unittest
from utils.metrics import weighted_sum, normalize, engagement_label, aggregate_windows


class MetricsTest(unittest.TestCase):

    def test_normalize_clamp(self):
        self.assertEqual(normalize(1.5), 1.0)
        self.assertEqual(normalize(-0.5), 0.0)
        self.assertAlmostEqual(normalize(0.5), 0.5)

    def test_weighted_sum_basic(self):
        signals = {"presence": 0.8, "motion": 0.4}
        weights = {"presence": 0.6, "motion": 0.4}
        result = weighted_sum(signals, weights)
        self.assertAlmostEqual(result, 0.8 * 0.6 + 0.4 * 0.4, places=4)

    def test_weighted_sum_partial_signals(self):
        signals = {"presence": 0.7}
        weights = {"presence": 0.5, "audio": 0.5}
        # Only presence is present; normalized weight = 1.0
        result = weighted_sum(signals, weights)
        self.assertAlmostEqual(result, 0.7, places=4)

    def test_weighted_sum_empty(self):
        self.assertEqual(weighted_sum({}, {"presence": 0.5}), 0.0)

    def test_engagement_label(self):
        self.assertEqual(engagement_label(0.9), "High")
        self.assertEqual(engagement_label(0.6), "Moderate")
        self.assertEqual(engagement_label(0.3), "Low")
        self.assertEqual(engagement_label(0.1), "Very Low")

    def test_aggregate_windows(self):
        windows = [
            {"composite_score": 0.3},
            {"composite_score": 0.5},
            {"composite_score": 0.7},
        ]
        result = aggregate_windows(windows)
        self.assertAlmostEqual(result["mean"], (0.3 + 0.5 + 0.7) / 3, places=4)
        self.assertEqual(result["trend"], "improving")
        self.assertEqual(result["low_engagement_windows"], 1)

    def test_aggregate_empty(self):
        self.assertEqual(aggregate_windows([]), {})


if __name__ == "__main__":
    unittest.main()
