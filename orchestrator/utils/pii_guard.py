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
    "Confirming Token",
    "Token Usage",
    "Claude API",
}
VALID_PII_MODES = {"strict", "standard", "off"}


def get_pii_mode(settings: dict | None = None) -> str:
    if not isinstance(settings, dict):
        return "strict"
    raw_mode = settings.get("pii", {}).get("mode", "strict")
    mode = str(raw_mode).strip().lower()
    return mode if mode in VALID_PII_MODES else "strict"


def contains_pii(text: str, mode: str = "strict") -> bool:
    if not text:
        return False
    normalized_mode = _normalize_mode(mode)
    if normalized_mode == "off":
        return False
    if EMAIL_PATTERN.search(text):
        return True
    return normalized_mode == "strict" and _contains_name_like_pii(text)


def sanitize_text(text: str, mode: str = "strict") -> str:
    if not text:
        return text
    normalized_mode = _normalize_mode(mode)
    if normalized_mode == "off":
        return text
    sanitized = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    if normalized_mode == "standard":
        return sanitized
    return NAME_PATTERN.sub(_replace_name_match, sanitized)


def _normalize_mode(mode: str) -> str:
    normalized = str(mode).strip().lower()
    return normalized if normalized in VALID_PII_MODES else "strict"


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
