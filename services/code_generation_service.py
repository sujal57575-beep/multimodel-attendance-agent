"""
services/code_generation_service.py
Educational code generation via AI gateway.
Generated code is NEVER executed automatically.
"""

from __future__ import annotations
import logging
from services.ai_gateway import AIGateway

logger = logging.getLogger(__name__)


class CodeGenerationService:

    def __init__(self):
        self._ai = AIGateway()

    def generate(self, topic: str, language: str = "python") -> dict:
        """
        Generate educational code example.
        Returns {code, language, topic, note, source}.
        """
        code = self._ai.generate_code_example(topic, language)
        return {
            "code": code,
            "language": language,
            "topic": topic,
            "source": "gemini" if self._ai.available else "template",
            "note": (
                "⚠️ This code is for educational purposes only. "
                "Review carefully before running. Code execution is disabled by default."
            ),
        }
