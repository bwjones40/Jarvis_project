"""Research agent for retrieving vault context."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from orchestrator.utils.pii_guard import get_pii_mode, sanitize_text
from orchestrator.utils.token_logger import log_agent_run
from orchestrator.utils.vault_reader import search_notes


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
        summary_lines = [f"- {sanitize_text(note['title'] or note['path'], mode=pii_mode)}" for note in notes] or ["- No matching vault notes found."]
        usage = type("Usage", (), {"input_tokens": 0, "output_tokens": 0})()
        output = {
            "context_summary": "Relevant vault context:\n" + "\n".join(summary_lines),
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
