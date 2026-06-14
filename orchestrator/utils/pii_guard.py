"""Simple PII detection and sanitization helpers for MVP safety guards."""

from __future__ import annotations

import re


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", flags=re.IGNORECASE)
NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b")
SAFE_PHRASES = {
    "Jarvis Inbox",
    "Draft Teams",
    "Teams Draft",
    "Nightly Digest",
    "Task ID",
    "Power Automate",
}


def contains_pii(text: str) -> bool:
    if not text:
        return False
    return bool(EMAIL_PATTERN.search(text) or _contains_name_like_pii(text))


def sanitize_text(text: str) -> str:
    if not text:
        return text
    sanitized = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    return NAME_PATTERN.sub(_replace_name_match, sanitized)


def _contains_name_like_pii(text: str) -> bool:
    for match in NAME_PATTERN.finditer(text):
        if match.group(1) not in SAFE_PHRASES:
            return True
    return False


def _replace_name_match(match: re.Match[str]) -> str:
    value = match.group(1)
    if value in SAFE_PHRASES:
        return value
    return "[REDACTED_NAME]"
