"""
services/recommendation_service.py
Rule-based offline recommendation engine + optional Gemini adapter.
Every recommendation is linked to measured evidence; no fabrication.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from config import Config
from utils.metrics import engagement_label

logger = logging.getLogger(__name__)


RULE_TEMPLATES = [
    {
        "id": "low_engagement_sustained",
        "condition": lambda s: s.get("low_engagement_windows", 0) >= 3,
        "title": "Sustained Low Engagement Detected",
        "observation": "Engagement indicators were below 0.35 for {low_engagement_windows} consecutive windows.",
        "suggestion": "Consider introducing an interactive activity such as a quick poll, think-pair-share, or comprehension check to re-engage participants.",
        "confidence": 0.72,
    },
    {
        "id": "engagement_declining",
        "condition": lambda s: s.get("trend") == "declining" and s.get("mean", 1) < 0.55,
        "title": "Declining Engagement Trend",
        "observation": "Composite engagement score declined from session start to end (trend: {trend}, mean: {mean:.2f}).",
        "suggestion": "Break the session with a 2-minute energiser or open a Q&A segment. Vary delivery method.",
        "confidence": 0.68,
    },
    {
        "id": "high_audio_low_visual",
        "condition": lambda s: s.get("audio_dominated", False),
        "title": "Instructor-Dominated Audio",
        "observation": "Audio activity is high but participant visual engagement is comparatively low.",
        "suggestion": "Introduce a group discussion or student presentation segment to balance instructor talk time.",
        "confidence": 0.60,
    },
    {
        "id": "low_attendance",
        "condition": lambda s: 0 < s.get("attendance_pct", 100) < 60,
        "title": "Low Attendance",
        "observation": "Only {attendance_pct:.0f}% of expected participants were detected.",
        "suggestion": "Review attendance records and follow up with absent participants. Consider recording sessions for asynchronous access.",
        "confidence": 0.85,
    },
    {
        "id": "good_engagement",
        "condition": lambda s: s.get("mean", 0) >= 0.65 and s.get("trend") != "declining",
        "title": "Strong Session Engagement",
        "observation": "Average engagement score was {mean:.2f} ({label}) with a {trend} trend.",
        "suggestion": "Session dynamics appear positive. Document successful strategies for future reference.",
        "confidence": 0.80,
    },
    {
        "id": "incomplete_data",
        "condition": lambda s: s.get("missing_signals", False),
        "title": "Incomplete Observational Data",
        "observation": "Some signals (audio or visual) were unavailable during this session.",
        "suggestion": "Review available data with appropriate caution. Manually verify attendance records where confidence is below 0.5.",
        "confidence": 0.90,
    },
]


class RecommendationService:

    def generate(
        self,
        session_id: str,
        session_summary: dict,
        audio_summary: dict,
        attendance_pct: float,
        time_range: dict | None = None,
    ) -> list[dict]:
        """
        Generate rule-based recommendations. Returns list of dicts ready for DB.
        """
        ctx = {
            **session_summary,
            "attendance_pct": attendance_pct,
            "label": engagement_label(session_summary.get("mean", 0)),
            "audio_dominated": (
                audio_summary.get("speech_dominant_windows", 0) >
                session_summary.get("window_count", 1) * 0.7
                and session_summary.get("mean", 0) < 0.5
            ),
            "missing_signals": bool(audio_summary.get("windows") == []),
        }

        recs = []
        for rule in RULE_TEMPLATES:
            try:
                if rule["condition"](ctx):
                    obs = rule["observation"].format(**ctx)
                    evidence = {
                        "mean_score": ctx.get("mean"),
                        "trend": ctx.get("trend"),
                        "low_windows": ctx.get("low_engagement_windows"),
                        "attendance_pct": ctx.get("attendance_pct"),
                    }
                    recs.append({
                        "id": uuid.uuid4().hex,
                        "session_id": session_id,
                        "title": rule["title"],
                        "observation": obs,
                        "evidence": json.dumps(evidence),
                        "suggestion": rule["suggestion"],
                        "confidence": rule["confidence"],
                        "time_range": json.dumps(time_range or {}),
                        "source": "rule",
                        "created_at": datetime.utcnow().isoformat(),
                    })
            except Exception as e:
                logger.warning("Rule %s evaluation error: %s", rule["id"], e)

        # Optionally augment with Gemini
        if Config.GEMINI_ENABLED and not recs:
            try:
                gemini_recs = self._gemini_recommendations(
                    session_id, ctx, time_range
                )
                recs.extend(gemini_recs)
            except Exception as e:
                logger.warning("Gemini recommendation failed: %s", e)

        if not recs:
            recs.append(self._no_data_rec(session_id))

        return recs

    # ── Gemini adapter ────────────────────────────────────────────────────

    def _gemini_recommendations(
        self, session_id: str, ctx: dict, time_range
    ) -> list[dict]:
        import google.generativeai as genai
        genai.configure(api_key=Config.GEMINI_API_KEY)
        model = genai.GenerativeModel(Config.GEMINI_MODEL)

        prompt = f"""
You are an educational analytics assistant. Based on the following session metrics, generate 2-3 specific, 
evidence-based teaching recommendations in JSON array format.

Session metrics:
{json.dumps(ctx, indent=2)}

Each recommendation must have:
- title (string)
- observation (string, factual, based only on the data above)
- evidence (object with metric values used)
- suggestion (string, specific actionable advice)
- confidence (float 0-1)

Return ONLY valid JSON array, no markdown.
"""
        response = model.generate_content(prompt)
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:-1])
        parsed = json.loads(raw)

        return [
            {
                "id": uuid.uuid4().hex,
                "session_id": session_id,
                "title": r.get("title", "AI Recommendation"),
                "observation": r.get("observation", ""),
                "evidence": json.dumps(r.get("evidence", {})),
                "suggestion": r.get("suggestion", ""),
                "confidence": float(r.get("confidence", 0.5)),
                "time_range": json.dumps(time_range or {}),
                "source": "gemini",
                "created_at": datetime.utcnow().isoformat(),
            }
            for r in parsed
        ]

    @staticmethod
    def _no_data_rec(session_id: str) -> dict:
        return {
            "id": uuid.uuid4().hex,
            "session_id": session_id,
            "title": "Insufficient Data for Recommendations",
            "observation": "Not enough session data is available to generate specific recommendations.",
            "evidence": json.dumps({}),
            "suggestion": "Ensure video and audio sources are correctly configured. Review session settings.",
            "confidence": 0.95,
            "time_range": json.dumps({}),
            "source": "rule",
            "created_at": datetime.utcnow().isoformat(),
        }
