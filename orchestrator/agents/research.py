"""Research agent for retrieving vault context."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from orchestrator.utils.pii_guard import sanitize_text
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
    threshold = settings.get("research", {}).get("cache_hit_threshold", 0.8)

    if notes and notes[0]["score"] >= threshold:
        summary = sanitize_text(notes[0]["content"])
        usage = type("Usage", (), {"input_tokens": 0, "output_tokens": 0})()
        output = {
            "context_summary": summary,
            "source_vault_paths": [note["path"] for note in notes],
            "cache_hit": True,
        }
    else:
        summary_lines = [f"- {sanitize_text(note['title'] or note['path'])}" for note in notes] or ["- No matching vault notes found."]
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
