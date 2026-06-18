from __future__ import annotations

import json
import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import anthropic
except ModuleNotFoundError:  # pragma: no cover - local fallback when dependency is absent
    anthropic = None

from orchestrator.utils.pii_guard import sanitize_text

VALIDATION_PROMPT = Path("prompts/validation.md").read_text(encoding="utf-8")
client = anthropic.Anthropic() if anthropic is not None and os.getenv("ANTHROPIC_API_KEY", "").strip() else None


@dataclass
class ValidationResult:
    confidence_score: float
    relevance: float
    completeness: float
    actionability: float
    format_adherence: float
    notes: str
    pass_: bool
    retry_recommended: bool
    escalate: bool


def score_output(
    agent_name: str,
    output_dict: dict,
    task_context: dict,
    run_id: str,
    thresholds: dict,
) -> ValidationResult:
    override = os.environ.get("JARVIS_VALIDATION_OVERRIDE_SCORE")
    if override is not None:
        return _synthetic_result(float(override), thresholds, notes="OVERRIDE")
    try:
        if client is None:
            raise RuntimeError("Anthropic client is unavailable")
        user_msg = json.dumps(
            {
                "agent": sanitize_text(agent_name, mode="strict"),
                "output": _sanitize_payload(output_dict),
                "task": _sanitize_payload(task_context),
                "run_id": sanitize_text(run_id, mode="strict"),
            },
            indent=2,
        )
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            system=VALIDATION_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = json.loads(_strip_code_fences(_extract_response_text(getattr(response, "content", []))))
        r = float(raw["relevance"])
        c = float(raw["completeness"])
        a = float(raw["actionability"])
        f = float(raw["format_adherence"])
        score = (r * 0.35) + (c * 0.30) + (a * 0.25) + (f * 0.10)
        pass_threshold = thresholds.get("pass_threshold", 0.90)
        retry_min = thresholds.get("retry_min_threshold", 0.60)
        return ValidationResult(
            confidence_score=round(score, 4),
            relevance=r,
            completeness=c,
            actionability=a,
            format_adherence=f,
            notes=str(raw.get("notes", ""))[:300],
            pass_=score >= pass_threshold,
            retry_recommended=retry_min <= score < pass_threshold,
            escalate=score < retry_min,
        )
    except Exception as exc:
        warnings.warn(f"Validation Agent error for {agent_name}: {exc}")
        return _synthetic_result(0.90, thresholds, notes="SYNTHETIC: Validation Agent error")


def _synthetic_result(score: float, thresholds: dict, notes: str = "SYNTHETIC") -> ValidationResult:
    pass_threshold = thresholds.get("pass_threshold", 0.90)
    retry_min = thresholds.get("retry_min_threshold", 0.60)
    return ValidationResult(
        confidence_score=score,
        relevance=score,
        completeness=score,
        actionability=score,
        format_adherence=score,
        notes=notes,
        pass_=score >= pass_threshold,
        retry_recommended=retry_min <= score < pass_threshold,
        escalate=score < retry_min,
    )


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences the model sometimes adds despite instructions."""
    import re
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_response_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for item in content or []:
        text = getattr(item, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value, mode="strict")
    return value
