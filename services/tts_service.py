"""
services/tts_service.py
Local TTS using pyttsx3 (offline). Saves audio on request.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)

try:
    import pyttsx3
    _engine_available = True
except ImportError:
    _engine_available = False
    logger.info("pyttsx3 not installed; TTS disabled")


class TTSService:
    def __init__(self):
        self._engine = None
        if _engine_available and Config.TTS_ENABLED:
            try:
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", 160)
                logger.info("TTS engine initialised (pyttsx3)")
            except Exception as e:
                logger.warning("TTS init failed: %s", e)

    @property
    def available(self) -> bool:
        return self._engine is not None

    def speak(self, text: str) -> bool:
        """Speak text aloud synchronously. Returns success flag."""
        if not self.available:
            return False
        try:
            self._engine.say(text[:1000])
            self._engine.runAndWait()
            return True
        except Exception as e:
            logger.error("TTS speak error: %s", e)
            return False

    def save(self, text: str, filename: str | None = None) -> str | None:
        """Save speech to WAV file. Returns path or None."""
        if not self.available:
            return None
        out_dir = Path(Config.GENERATED_AUDIO_FOLDER)
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = filename or f"tts_{uuid.uuid4().hex}.wav"
        out_path = str(out_dir / fname)
        try:
            self._engine.save_to_file(text[:2000], out_path)
            self._engine.runAndWait()
            logger.info("TTS saved → %s", out_path)
            return out_path
        except Exception as e:
            logger.error("TTS save error: %s", e)
            return None
