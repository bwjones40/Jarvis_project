"""Orchestrator agent for building the TaskResult skeleton."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from orchestrator.utils.pii_guard import contains_pii, get_pii_mode, sanitize_text
from orchestrator.utils.token_logger import log_agent_run


def run_orchestrator(
    task: dict[str, Any],
    vault_notes: list[dict[str, Any]],
    settings: dict[str, Any],
) -> dict[str, Any]:
    start = perf_counter()
    pii_mode = get_pii_mode(settings)
    sanitized_task = {key: sanitize_text(value, mode=pii_mode) if isinstance(value, str) else value for key, value in task.items()}
    clarifications_needed: list[str] = []
    status = "completed"
    if any(contains_pii(str(task.get(field, "")), mode=pii_mode) for field in ("title", "request", "context", "copilot_handoff")):
        clarifications_needed.append("PII detected in input. Remove names, email addresses, and customer data before rerunning.")
        status = "needs_clarification"
        sanitized_task["request"] = "Input withheld because it contained PII."
        sanitized_task["context"] = ""
        sanitized_task["copilot_handoff"] = ""
    elif _needs_clarification(sanitized_task["request"]):
        clarifications_needed.append("Task request is too ambiguous. Add the missing context and rerun.")
        status = "needs_clarification"

    routing = _build_routing(task.get("agents_needed", []), sanitized_task["mode"])
    task_result = {
        "task_id": _build_task_id(sanitized_task["title"]),
        "task_title": sanitized_task["title"],
        "run_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "mode": sanitized_task["mode"],
        "status": status,
        "agents_executed": [],
        "output_summary": "Task parsed and routed for execution.",
        "draft_communications": [],
        "clarifications_needed": clarifications_needed,
        "knowledge_updates": [],
        "routing": routing,
        "task": sanitized_task,
    }

    usage = type("Usage", (), {"input_tokens": 0, "output_tokens": 0})()
    agent_output = {
        "plan": f"Route to {', '.join(routing['agents_to_run'])}" if routing["agents_to_run"] else "No downstream agents required.",
        "knowledge_context_used": [note["path"] for note in vault_notes[:3]],
        "clarifications_needed": clarifications_needed,
    }
    task_result["agents_executed"].append(
        log_agent_run(
            agent_name="orchestrator",
            model=settings.get("models", {}).get("orchestrator", "claude-sonnet-4-6"),
            usage=usage,
            duration=perf_counter() - start,
            output=agent_output,
            errors=[],
        )
    )
    return task_result


def _build_routing(agents_needed: list[str], mode: str) -> dict[str, list[str]]:
    requested = [agent for agent in agents_needed if agent != "orchestrator"]
    routed: list[str] = []
    for agent in requested:
        if agent == "gcp" and mode != "daytime":
            continue
        if agent not in routed:
            routed.append(agent)
    if "obsidian" not in routed:
        routed.append("obsidian")
    return {"agents_to_run": routed}


def _build_task_id(title: str) -> str:
    slug = "-".join(part for part in "".join(char.lower() if char.isalnum() else "-" for char in title).split("-") if part)
    return f"task-001-{slug or 'untitled-task'}"


def _needs_clarification(request: str) -> bool:
    normalized = request.strip().lower()
    if not normalized:
        return True
    placeholders = {
        "describe the task jarvis should complete before the next run.",
        "todo",
        "tbd",
    }
    return normalized in placeholders
