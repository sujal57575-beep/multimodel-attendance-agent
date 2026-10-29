"""
services/audio_processor.py
Extracts audio from video, computes VAD and activity timelines.
"""

from __future__ import annotations

import logging
import os
import subprocess
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import numpy as np
    import soundfile as sf
    SOUNDFILE_OK = True
except ImportError:
    SOUNDFILE_OK = False
    logger.warning("soundfile not installed; audio analysis disabled")

try:
    import librosa
    LIBROSA_OK = True
except ImportError:
    LIBROSA_OK = False
    logger.warning("librosa not installed; audio features unavailable")


class AudioProcessor:

    def extract_audio(self, video_path: str, out_dir: str) -> Optional[str]:
        """Extract WAV from video using ffmpeg. Returns path or None."""
        out_path = str(Path(out_dir) / f"{uuid.uuid4().hex}.wav")
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", video_path,
                    "-vn", "-acodec", "pcm_s16le",
                    "-ar", "16000", "-ac", "1",
                    out_path,
                ],
                capture_output=True,
                timeout=300,
            )
            if result.returncode == 0 and Path(out_path).exists():
                logger.info("Audio extracted → %s", out_path)
                return out_path
            logger.warning("ffmpeg failed: %s", result.stderr.decode()[:300])
            return None
        except FileNotFoundError:
            logger.warning("ffmpeg not found; audio extraction skipped")
            return None
        except Exception as e:
            logger.error("Audio extraction error: %s", e)
            return None

    def analyse(self, audio_path: str, window_seconds: int = 60) -> dict:
        """
        Compute per-window audio activity metrics.
        Returns dict with keys: windows, session_summary.
        """
        if not SOUNDFILE_OK or not LIBROSA_OK:
            return self._unavailable_result()

        try:
            y, sr = librosa.load(audio_path, sr=16000, mono=True)
        except Exception as e:
            logger.error("Cannot load audio %s: %s", audio_path, e)
            return self._unavailable_result()

        total_seconds = len(y) / sr
        frame_length = int(0.025 * sr)   # 25 ms
        hop_length = int(0.010 * sr)     # 10 ms

        # Energy-based VAD
        rms = librosa.feature.rms(y=y, frame_length=frame_length,
                                  hop_length=hop_length)[0]
        rms_norm = rms / (rms.max() + 1e-9)
        vad = rms_norm > 0.05            # crude threshold

        times = librosa.frames_to_time(
            range(len(rms)), sr=sr, hop_length=hop_length
        )

        windows = []
        idx = 0
        w_start = 0.0
        while w_start < total_seconds:
            w_end = min(w_start + window_seconds, total_seconds)
            mask = (times >= w_start) & (times < w_end)
            if mask.sum() == 0:
                w_start = w_end
                idx += 1
                continue

            seg_vad = vad[mask]
            seg_rms = rms_norm[mask]
            speech_frames = seg_vad.sum()
            total_frames = len(seg_vad)

            activity_ratio = float(speech_frames / total_frames) if total_frames else 0
            avg_energy = float(seg_rms.mean())

            windows.append({
                "window_index": idx,
                "window_start_seconds": round(w_start, 2),
                "window_end_seconds": round(w_end, 2),
                "activity_ratio": round(activity_ratio, 4),
                "avg_energy": round(avg_energy, 4),
                "speech_seconds": round(activity_ratio * (w_end - w_start), 2),
                "silence_seconds": round((1 - activity_ratio) * (w_end - w_start), 2),
                "audio_score": round(min(activity_ratio * 2, 1.0), 4),   # rescaled
            })
            w_start = w_end
            idx += 1

        scores = [w["audio_score"] for w in windows]
        session_summary = {
            "total_seconds": round(total_seconds, 2),
            "avg_audio_score": round(sum(scores) / len(scores), 4) if scores else 0,
            "speech_dominant_windows": sum(1 for w in windows if w["activity_ratio"] > 0.5),
            "silent_windows": sum(1 for w in windows if w["activity_ratio"] < 0.05),
            "note": "Audio activity indicates sound/speech presence, not student engagement.",
        }
        return {"windows": windows, "session_summary": session_summary}

    @staticmethod
    def _unavailable_result() -> dict:
        return {
            "windows": [],
            "session_summary": {
                "note": "Audio analysis unavailable (librosa/soundfile not installed or ffmpeg missing)."
            },
        }
