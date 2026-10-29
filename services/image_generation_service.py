"""
services/image_generation_service.py
Optional educational image generation adapter.
Uses Gemini Imagen API if available; falls back to placeholder notice.
"""

from __future__ import annotations
import logging
from config import Config

logger = logging.getLogger(__name__)


class ImageGenerationService:

    def __init__(self):
        self._available = False
        if Config.GEMINI_ENABLED:
            try:
                import google.generativeai as genai
                genai.configure(api_key=Config.GEMINI_API_KEY)
                self._client = genai
                self._available = True
                logger.info("Image generation service ready (Gemini)")
            except Exception as e:
                logger.warning("Image generation unavailable: %s", e)

    @property
    def available(self) -> bool:
        return self._available

    def generate_diagram(self, topic: str, style: str = "educational") -> dict:
        """
        Generate an educational diagram. Returns {available, url_or_path, note}.
        When offline, returns a descriptive note instead of an image.
        """
        if not self._available:
            return {
                "available": False,
                "note": (
                    f"Image generation is offline. "
                    f"Suggested diagram topic: '{topic}'. "
                    "Enable GEMINI_API_KEY in .env for AI-generated visuals."
                ),
            }
        # Gemini image generation would go here when the API supports it
        return {
            "available": False,
            "note": "Image generation API not yet supported in this configuration.",
        }
