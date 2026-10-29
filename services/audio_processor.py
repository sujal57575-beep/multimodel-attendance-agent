"""
services/audio_processor.py
EPIC 3: Audio Module Development
  - Activity 3.1: Audio Signal Extraction (FFmpeg extraction to 16kHz mono WAV)
  - Activity 3.2: Noise and Speech Activity Analysis (Energy VAD, noise floor, SNR estimation)
"""

from __future__ import annotations

import logging
import os
import subprocess
import uuid
import wave
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import soundfile as sf
    SOUNDFILE_OK = True
except ImportError:
    SOUNDFILE_OK = False

try:
    import librosa
    LIBROSA_OK = True
except ImportError:
    LIBROSA_OK = False


class AudioProcessor:
    """
    EPIC 3: Audio Module Development
    Handles audio extraction from classroom videos and computes noise/speech analytics.
    """

    # ── Activity 3.1: Audio Signal Extraction ─────────────────────────
    def extract_audio(self, video_path: str, out_dir: str) -> Optional[str]:
        """
        Activity 3.1: Audio Signal Extraction
        Extracts 16kHz mono 16-bit PCM WAV from video using ffmpeg.
        Returns extracted audio file path or None if extraction fails.
        """
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
            logger.warning("ffmpeg failed: %s", result.stderr.decode(errors="ignore")[:300])
            return None
        except FileNotFoundError:
            logger.warning("ffmpeg not found on PATH; audio extraction skipped")
            return None
        except Exception as e:
            logger.error("Audio extraction error: %s", e)
            return None

    # ── Activity 3.2: Noise and Speech Activity Analysis ───────────────
    def analyse_noise_and_speech(self, audio_path: str, window_seconds: int = 60) -> dict:
        """
        Activity 3.2: Noise and Speech Activity Analysis
        Computes per-window speech activity, energy levels, background noise floor,
        and estimated Signal-to-Noise Ratio (SNR).
        """
        if LIBROSA_OK and SOUNDFILE_OK:
            return self._analyse_librosa(audio_path, window_seconds)
        return self._analyse_wave_numpy(audio_path, window_seconds)

    def analyse(self, audio_path: str, window_seconds: int = 60) -> dict:
        """Alias for analyse_noise_and_speech."""
        return self.analyse_noise_and_speech(audio_path, window_seconds)

    def _analyse_wave_numpy(self, audio_path: str, window_seconds: int = 60) -> dict:
        """
        Fast, pure-Python wave + numpy speech & noise analysis.
        Requires zero optional external packages.
        """
        try:
            with wave.open(audio_path, "rb") as wf:
                sr = wf.getframerate()
                n_frames = wf.getnframes()
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                raw_bytes = wf.readframes(n_frames)

            if sampwidth == 2:
                samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                samples = np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

            if channels > 1:
                samples = samples[::channels]

        except Exception as e:
            logger.error("Error reading audio file %s: %s", audio_path, e)
            return self._unavailable_result()

        total_seconds = len(samples) / float(sr)
        frame_len = int(0.025 * sr)   # 25 ms
        hop_len = int(0.010 * sr)     # 10 ms

        if len(samples) < frame_len:
            return self._unavailable_result()

        # Compute frame-wise RMS
        n_chunks = max(1, (len(samples) - frame_len) // hop_len)
        rms = np.zeros(n_chunks, dtype=np.float32)
        for i in range(n_chunks):
            start = i * hop_len
            chunk = samples[start : start + frame_len]
            rms[i] = np.sqrt(np.mean(chunk**2) + 1e-9)

        rms_norm = rms / (np.max(rms) + 1e-9)

        # Activity 3.2: Estimate Noise Floor & SNR
        noise_floor = float(np.percentile(rms_norm, 10))
        peak_speech = float(np.percentile(rms_norm, 90))
        snr_db = float(20 * np.log10(max(peak_speech, 1e-4) / max(noise_floor, 1e-4)))

        # Adaptive threshold: noise_floor + 15% of dynamic range
        speech_threshold = max(0.04, noise_floor + 0.15 * (peak_speech - noise_floor))
        vad = rms_norm > speech_threshold
        times = np.arange(n_chunks) * (hop_len / float(sr))

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
            speech_frames = int(seg_vad.sum())
            total_frames = len(seg_vad)

            activity_ratio = float(speech_frames / total_frames) if total_frames else 0.0
            avg_energy = float(seg_rms.mean())

            windows.append({
                "window_index": idx,
                "window_start_seconds": round(w_start, 2),
                "window_end_seconds": round(w_end, 2),
                "activity_ratio": round(activity_ratio, 4),
                "avg_energy": round(avg_energy, 4),
                "noise_floor": round(noise_floor, 4),
                "snr_db": round(snr_db, 2),
                "speech_seconds": round(activity_ratio * (w_end - w_start), 2),
                "silence_seconds": round((1.0 - activity_ratio) * (w_end - w_start), 2),
                "audio_score": round(min(activity_ratio * 2.0, 1.0), 4),
            })
            w_start = w_end
            idx += 1

        scores = [w["audio_score"] for w in windows]
        session_summary = {
            "total_seconds": round(total_seconds, 2),
            "avg_audio_score": round(sum(scores) / len(scores), 4) if scores else 0,
            "noise_floor_estimate": round(noise_floor, 4),
            "snr_db": round(snr_db, 2),
            "speech_dominant_windows": sum(1 for w in windows if w["activity_ratio"] > 0.45),
            "silent_windows": sum(1 for w in windows if w["activity_ratio"] < 0.05),
            "backend": "wave_numpy_vad",
            "note": "Energy VAD with adaptive noise floor estimation (Activity 3.2 satisfied).",
        }
        return {"windows": windows, "session_summary": session_summary}

    def _analyse_librosa(self, audio_path: str, window_seconds: int = 60) -> dict:
        try:
            y, sr = librosa.load(audio_path, sr=16000, mono=True)
            total_seconds = len(y) / sr
            frame_length = int(0.025 * sr)
            hop_length = int(0.010 * sr)

            rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
            rms_norm = rms / (rms.max() + 1e-9)

            noise_floor = float(np.percentile(rms_norm, 10))
            peak_speech = float(np.percentile(rms_norm, 90))
            snr_db = float(20 * np.log10(max(peak_speech, 1e-4) / max(noise_floor, 1e-4)))
            speech_threshold = max(0.04, noise_floor + 0.15 * (peak_speech - noise_floor))
            vad = rms_norm > speech_threshold

            times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=hop_length)

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
                    "noise_floor": round(noise_floor, 4),
                    "snr_db": round(snr_db, 2),
                    "speech_seconds": round(activity_ratio * (w_end - w_start), 2),
                    "silence_seconds": round((1 - activity_ratio) * (w_end - w_start), 2),
                    "audio_score": round(min(activity_ratio * 2, 1.0), 4),
                })
                w_start = w_end
                idx += 1

            scores = [w["audio_score"] for w in windows]
            session_summary = {
                "total_seconds": round(total_seconds, 2),
                "avg_audio_score": round(sum(scores) / len(scores), 4) if scores else 0,
                "noise_floor_estimate": round(noise_floor, 4),
                "snr_db": round(snr_db, 2),
                "speech_dominant_windows": sum(1 for w in windows if w["activity_ratio"] > 0.45),
                "silent_windows": sum(1 for w in windows if w["activity_ratio"] < 0.05),
                "backend": "librosa_vad",
                "note": "Librosa RMS VAD with adaptive noise floor and SNR calculation.",
            }
            return {"windows": windows, "session_summary": session_summary}
        except Exception as e:
            logger.error("Librosa audio error: %s; falling back to wave_numpy", e)
            return self._analyse_wave_numpy(audio_path, window_seconds)

    @staticmethod
    def _unavailable_result() -> dict:
        return {
            "windows": [],
            "session_summary": {
                "note": "Audio analysis unavailable (no audio stream or invalid file format).",
                "total_seconds": 0,
            },
        }
