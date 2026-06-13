"""Simple PII detection and sanitization helpers for MVP safety guards."""

from __future__ import annotations

import re


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", flags=re.IGNORECASE)


def contains_pii(text: str) -> bool:
    if not text:
        return False
    return bool(EMAIL_PATTERN.search(text))


def sanitize_text(text: str) -> str:
    if not text:
        return text
    return EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
