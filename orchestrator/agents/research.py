"""Research agent for retrieving vault context."""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from time import perf_counter, sleep
from typing import Any

try:
    import anthropic
except ModuleNotFoundError:  # pragma: no cover - local fallback when dependency is absent
    anthropic = None

from orchestrator.utils.pii_guard import get_pii_mode, sanitize_text
from orchestrator.utils.token_logger import log_agent_run
from orchestrator.utils.vault_reader import search_notes

agent_version = "1.0.0"

RESEARCH_PROMPT = Path("prompts/research.md").read_text(encoding="utf-8")
client = anthropic.Anthropic() if anthropic is not None and os.getenv("ANTHROPIC_API_KEY", "").strip() else None


def run_research(
    task_result: dict[str, Any],
    settings: dict[str, Any],
    vault_root: str,
) -> dict[str, Any]:
    start = perf_counter()
    task = task_result["task"]
    notes = search_notes(task["request"], vault_root, max_results=settings.get("research", {}).get("max_context_notes", 3))
    research_settings = settings.get("research", {})
    pii_mode = get_pii_mode(settings)
    threshold = research_settings.get("cache_hit_threshold", 0.8)
    max_tokens_per_note = int(research_settings.get("max_tokens_per_note", 2000))

    if notes and notes[0]["score"] >= threshold:
        summary = _cap_note_content(sanitize_text(notes[0]["content"], mode=pii_mode), max_tokens_per_note)
        usage = type("Usage", (), {"input_tokens": 0, "output_tokens": 0})()
        output = {
            "context_summary": summary,
            "source_vault_paths": [note["path"] for note in notes],
            "cache_hit": True,
        }
    else:
        response = _call_research_model(_sanitize_for_anthropic(task["request"]))
        if response is None:
            summary_lines = [f"- {sanitize_text(note['title'] or note['path'], mode=pii_mode)}" for note in notes] or ["- No matching vault notes found."]
            usage = type("Usage", (), {"input_tokens": 0, "output_tokens": 0})()
            output = {
                "context_summary": "Relevant vault context:\n" + "\n".join(summary_lines),
                "source_vault_paths": [note["path"] for note in notes],
                "cache_hit": False,
            }
        else:
            usage = getattr(response, "usage", type("Usage", (), {"input_tokens": 0, "output_tokens": 0})())
            output = {
                "context_summary": _extract_response_text(getattr(response, "content", [])) or "Relevant vault context unavailable.",
                "source_vault_paths": [note["path"] for note in notes],
                "cache_hit": False,
            }

    task_result["research_summary"] = output["context_summary"]
    task_result["research_sources"] = output["source_vault_paths"]
    task_result["agents_executed"].append(
        log_agent_run(
            agent_name="research",
            model=settings.get("models", {}).get("subagent", "claude-haiku-4-5"),
            usage=usage,
            duration=perf_counter() - start,
            output=output,
            errors=[],
        )
    )
    if output["context_summary"] and task_result["status"] == "completed":
        task_result["output_summary"] = "Vault context retrieved and summarized."
    return task_result


def _cap_note_content(content: str, max_tokens: int) -> str:
    words = content.split()
    if max_tokens <= 0 or len(words) <= max_tokens:
        return content
    return " ".join(words[:max_tokens]) + "\n\n[Context truncated to configured note token cap.]"


def _call_research_model(prompt_text: str) -> Any | None:
    """Call the research model, degrading to ``None`` instead of raising.

    A ``None`` return is handled by the caller as a graceful fallback (a summary
    built from vault note titles), so a transient outage or a bad/expired API key
    never halts the pipeline. Auth/permission failures skip the retry since they
    will not clear on their own.
    """
    if client is None or anthropic is None:
        return None

    def _create() -> Any:
        return client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=RESEARCH_PROMPT,
            messages=[{"role": "user", "content": prompt_text}],
        )

    try:
        return _create()
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        warnings.warn(f"Research model call failed (auth/permission); using degraded fallback: {exc}")
        return None
    except anthropic.APIError:
        sleep(10)
        try:
            return _create()
        except anthropic.APIError as exc:
            warnings.warn(f"Research model call failed after retry; using degraded fallback: {exc}")
            return None


def _extract_response_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for item in content or []:
        text = getattr(item, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def _sanitize_for_anthropic(text: str) -> str:
    return sanitize_text(text, mode="strict")
