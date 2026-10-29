"""
utils/validators.py — Input validation helpers
"""

import re
from typing import Any


def require_fields(data: dict, fields: list[str]) -> list[str]:
    """Return list of missing required field names."""
    return [f for f in fields if not data.get(f)]


def is_valid_session_name(name: str) -> bool:
    return bool(name) and 1 <= len(name.strip()) <= 200


def is_valid_identifier(val: str) -> bool:
    """Alphanumeric + dash/underscore only, 1-100 chars."""
    return bool(re.match(r"^[\w\-]{1,100}$", val or ""))


def sanitize_text(text: str, max_len: int = 500) -> str:
    """Strip and truncate text input."""
    return (text or "").strip()[:max_len]
