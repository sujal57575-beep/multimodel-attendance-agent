"""
services/ai_gateway.py
Provider-independent AI interface (Gemini / rule-based fallback).
"""

from __future__ import annotations

import json
import logging
from config import Config

logger = logging.getLogger(__name__)


class AIGateway:

    def __init__(self):
        self._gemini = None
        if Config.GEMINI_ENABLED:
            try:
                import google.generativeai as genai
                genai.configure(api_key=Config.GEMINI_API_KEY)
                self._gemini = genai.GenerativeModel(Config.GEMINI_MODEL)
                logger.info("Gemini model initialised: %s", Config.GEMINI_MODEL)
            except Exception as e:
                logger.warning("Gemini init failed: %s", e)

    @property
    def available(self) -> bool:
        return self._gemini is not None

    def summarise_session(self, metrics: dict) -> str:
        prompt = f"""
Summarise this classroom session in 3-4 sentences for a teacher.
Metrics: {json.dumps(metrics)}
Be factual, concise, and avoid speculation. Mention data gaps if present.
"""
        return self._generate(prompt, fallback=self._rule_summary(metrics))

    def generate_quiz(self, topic: str, count: int = 5) -> str:
        prompt = f"""
Generate {count} multiple-choice quiz questions on the topic: '{topic}'.
Format as JSON array with keys: question, options (array of 4), answer (index 0-3).
Return ONLY valid JSON.
"""
        return self._generate(prompt, fallback="[]")

    def generate_code_example(self, topic: str, language: str = "python") -> str:
        prompt = f"""
Write a short, educational {language} code example demonstrating: '{topic}'.
Include comments. Return only code, no markdown fences.
"""
        return self._generate(prompt, fallback=f"# {language} example for: {topic}\npass")

    def _generate(self, prompt: str, fallback: str = "") -> str:
        if not self._gemini:
            return fallback
        try:
            response = self._gemini.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.warning("Gemini generation failed: %s", e)
            return fallback

    @staticmethod
    def _rule_summary(metrics: dict) -> str:
        mean = metrics.get("mean", 0)
        trend = metrics.get("trend", "unknown")
        windows = metrics.get("window_count", 0)
        return (
            f"Session summary ({windows} time windows analysed): "
            f"Average engagement score was {mean:.2f} with a {trend} trend. "
            f"Low-engagement windows: {metrics.get('low_engagement_windows', 0)}. "
            "Review AI teaching recommendations for specific suggestions."
        )
