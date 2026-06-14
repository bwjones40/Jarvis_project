"""Parse the operator-managed Jarvis inbox markdown file."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


VALID_PRIORITIES = {"high", "medium", "low"}
VALID_MODES = {"overnight", "daytime"}
VALID_AGENTS = {"orchestrator", "research", "gcp", "obsidian"}
TEMPLATE_TITLE = "Replace this title before commit"
TEMPLATE_REQUEST = "Describe the task Jarvis should complete before the next run."
TEMPLATE_CONTEXT = "Optional project context, links, or non-PII background."
TEMPLATE_COPILOT_HANDOFF = "Optional manual handoff instructions for Copilot."


class InboxParseError(ValueError):
    """Raised when the inbox content violates the contract."""


def parse_inbox(inbox_path: str | Path) -> dict[str, Any] | None:
    path = Path(inbox_path)
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return None

    task_match = re.search(r"^## Task:\s*(.+)$", content, flags=re.MULTILINE)
    if not task_match:
        raise InboxParseError("Inbox must contain a '## Task:' heading.")

    first_task_start = task_match.start()
    remaining = content[first_task_start:]
    next_task_match = re.search(r"^## Task:\s*(.+)$", remaining[task_match.end() - first_task_start :], flags=re.MULTILINE)
    if next_task_match:
        remaining = remaining[: task_match.end() - first_task_start + next_task_match.start()]

    title = task_match.group(1).strip()
    if not title:
        raise InboxParseError("Task title is required.")
    if len(title) > 80:
        raise InboxParseError("Task title must be 80 characters or fewer.")

    fields = _parse_fields(remaining)
    priority = fields.get("priority", "").lower()
    if priority not in VALID_PRIORITIES:
        raise InboxParseError("Priority must be one of: high, medium, low.")

    mode = fields.get("mode", "").lower()
    if mode not in VALID_MODES:
        raise InboxParseError("Mode must be one of: overnight, daytime.")

    agents_needed = _parse_agents(fields.get("agents needed", ""))
    request = _extract_section(remaining, "Request")
    if not request:
        raise InboxParseError("Request section is required and cannot be empty.")

    context = _extract_section(remaining, "Context")
    copilot_handoff = _extract_section(remaining, "Copilot handoff")
    if _is_template_task(title, request, context, copilot_handoff):
        return None

    return {
        "title": title,
        "priority": priority,
        "mode": mode,
        "agents_needed": agents_needed,
        "due": fields.get("due", "next run").strip() or "next run",
        "request": request,
        "context": context,
        "copilot_handoff": copilot_handoff,
    }


def _parse_fields(content: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in re.finditer(r"^\*\*(.+?)\*\*:\s*(.+)$", content, flags=re.MULTILINE):
        fields[match.group(1).strip().lower()] = match.group(2).strip()
    return fields


def _parse_agents(raw_value: str) -> list[str]:
    agents = ["orchestrator"]
    if raw_value.strip():
        for agent in [item.strip().lower() for item in raw_value.split(",")]:
            if not agent:
                continue
            if agent not in VALID_AGENTS:
                raise InboxParseError(f"Agents needed contains unsupported agent '{agent}'.")
            if agent not in agents:
                agents.append(agent)
    return agents


def _extract_section(content: str, heading: str) -> str:
    pattern = re.compile(
        rf"^### {re.escape(heading)}\s*$\n(.*?)(?=^### |\n---\s*$|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        return ""
    return match.group(1).strip()


def _is_template_task(title: str, request: str, context: str, copilot_handoff: str) -> bool:
    return (
        title == TEMPLATE_TITLE
        and request == TEMPLATE_REQUEST
        and context == TEMPLATE_CONTEXT
        and copilot_handoff == TEMPLATE_COPILOT_HANDOFF
    )
