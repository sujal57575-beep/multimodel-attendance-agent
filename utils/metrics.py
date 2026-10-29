"""
utils/metrics.py — Engagement metric aggregation helpers
"""

from __future__ import annotations
import math
from typing import Sequence


def normalize(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp and normalize a value to [0, 1]."""
    if max_val == min_val:
        return 0.0
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def weighted_sum(signals: dict[str, float], weights: dict[str, float]) -> float:
    """
    Compute a weighted engagement score.
    Only uses signals present in both dicts; normalises weights of present signals.
    """
    active = {k: v for k, v in signals.items() if k in weights}
    if not active:
        return 0.0
    total_weight = sum(weights[k] for k in active)
    if total_weight == 0:
        return 0.0
    score = sum(active[k] * weights[k] for k in active) / total_weight
    return round(max(0.0, min(1.0, score)), 4)


def engagement_label(score: float) -> str:
    if score >= 0.75:
        return "High"
    if score >= 0.50:
        return "Moderate"
    if score >= 0.25:
        return "Low"
    return "Very Low"


def moving_average(values: Sequence[float], window: int = 3) -> list[float]:
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        result.append(sum(chunk) / len(chunk))
    return result


def aggregate_windows(metrics: list[dict]) -> dict:
    """Aggregate a list of window metric dicts into a session summary."""
    if not metrics:
        return {}
    scores = [m.get("composite_score", 0) for m in metrics]
    return {
        "mean": round(sum(scores) / len(scores), 4),
        "min": round(min(scores), 4),
        "max": round(max(scores), 4),
        "trend": "improving" if scores[-1] > scores[0] else "declining" if scores[-1] < scores[0] else "stable",
        "window_count": len(scores),
        "low_engagement_windows": sum(1 for s in scores if s < 0.35),
    }
