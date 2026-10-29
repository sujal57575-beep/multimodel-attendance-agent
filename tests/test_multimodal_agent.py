"""
tests/test_multimodal_agent.py
EPIC 4 & EPIC 6 Unit Tests:
  - Activity 4.1: Multimodal Agent Implementation
  - Activity 4.2: Multimodal Signal Fusion
  - Activity 4.3: Engagement Scoring Logic
  - Activity 6.3: Validate Outputs and Edge Cases
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from services.multimodal_agent import MultimodalAttendanceAgent
from services.audio_processor import AudioProcessor
from utils.metrics import weighted_sum, moving_average, aggregate_windows


class MultimodalAgentTest(unittest.TestCase):

    def setUp(self):
        self.agent = MultimodalAttendanceAgent()

    def test_agent_initialization(self):
        """Activity 4.1: Verify agent components are properly initialized."""
        self.assertIsNotNone(self.agent.video_processor)
        self.assertIsNotNone(self.agent.audio_processor)
        self.assertIsNotNone(self.agent.engagement_service)
        self.assertIsNotNone(self.agent.attendance_service)
        self.assertIsNotNone(self.agent.recommendation_service)

    def test_signal_fusion_weights(self):
        """Activity 4.2: Multimodal Signal Fusion weights verification."""
        signals = {
            "presence": 0.8,
            "motion": 0.5,
            "audio_activity": 0.6,
            "head_pose": 0.7,
        }
        score = weighted_sum(signals, Config.ENGAGEMENT_WEIGHTS)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_engagement_scoring_logic_and_smoothing(self):
        """Activity 4.3: Engagement Scoring Logic and moving average smoothing."""
        raw_scores = [0.2, 0.3, 0.8, 0.9, 0.4]
        smoothed = moving_average(raw_scores, window=3)
        self.assertEqual(len(smoothed), len(raw_scores))
        # Moving average should smooth out spikes
        self.assertLess(smoothed[2], 0.8)

    def test_edge_case_missing_audio(self):
        """Activity 6.3: Edge case - video with no audio stream."""
        video_windows = [
            {
                "window_index": 0,
                "window_start_seconds": 0,
                "window_end_seconds": 60,
                "presence_score": 0.85,
                "motion_score": 0.30,
                "head_pose_score": 0.90,
                "max_participant_count": 5,
            }
        ]
        # Empty audio windows simulates silent or audio-less video
        metrics = self.agent.engagement_service.compute(
            session_id="test_no_audio",
            video_windows=video_windows,
            audio_windows=[],
            fps=25.0,
            session_start=datetime.now(),
        )
        self.assertEqual(len(metrics), 1)
        self.assertIn("audio", metrics[0]["missing_data"])
        self.assertEqual(metrics[0]["confidence"], 0.65)
        self.assertGreater(metrics[0]["composite_score"], 0)

    def test_edge_case_empty_classroom(self):
        """Activity 6.3: Edge case - empty room with zero detected participants."""
        video_windows = [
            {
                "window_index": 0,
                "window_start_seconds": 0,
                "window_end_seconds": 60,
                "presence_score": 0.0,
                "motion_score": 0.0,
                "head_pose_score": 0.0,
                "max_participant_count": 0,
            }
        ]
        metrics = self.agent.engagement_service.compute(
            session_id="test_empty",
            video_windows=video_windows,
            audio_windows=[],
            fps=25.0,
            session_start=datetime.now(),
        )
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["composite_score"], 0.0)

    def test_edge_case_short_session(self):
        """Activity 6.3: Edge case - participant present less than attendance threshold."""
        from services.video_processor import TrackedParticipant
        p = TrackedParticipant(
            track_id="short_track",
            first_frame=0,
            last_frame=250,
            first_time=0.0,
            last_time=20.0, # only 20 seconds
            face_detected_count=1,
        )
        # Below 120s threshold -> should not be marked present
        self.assertFalse(p.total_duration >= Config.ATTENDANCE_THRESHOLD_SECONDS)
        self.assertFalse(p.attendance_marked)

    def test_audio_noise_and_speech_analysis(self):
        """Activity 3.2: Noise and speech analysis edge cases."""
        processor = AudioProcessor()
        res = processor.analyse_noise_and_speech("non_existent_file.wav")
        self.assertIn("windows", res)
        self.assertIn("session_summary", res)


if __name__ == "__main__":
    unittest.main()
