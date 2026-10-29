"""
services/participant_tracker.py
Re-exports VideoProcessor for semantic clarity in imports.
The centroid tracker is implemented inside video_processor.py.
"""

from services.video_processor import VideoProcessor, TrackedParticipant, ProcessingResult

__all__ = ["VideoProcessor", "TrackedParticipant", "ProcessingResult"]
