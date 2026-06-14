"""Build vault-ready markdown outputs from task results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from orchestrator.utils.pii_guard import sanitize_text
from orchestrator.utils.token_logger import calculate_cost, log_agent_run
from orchestrator.utils.vault_reader import note_exists, read_note


def build_vault_outputs(
    task_result: dict[str, Any] | None,
    task: dict[str, Any] | None,
    settings: dict[str, Any],
    vault_root: str = ".",
) -> list[dict[str, str]]:
    vault_settings = settings.get("vault", {})
    digest_path = f"{vault_settings.get('digests_dir', 'jarvis/digests')}/{_today_string()}.md"
    if task_result is None:
        return [{"vault_path": digest_path, "content": _build_empty_digest()}]

    usage = type("Usage", (), {"input_tokens": 0, "output_tokens": 0})()
    task_result["draft_communications"] = _stage_draft_communications(task_result, task or {})
    task_file_path = f"{vault_settings.get('tasks_dir', 'jarvis/tasks')}/{task_result['task_id']}.md"
    task_result["agents_executed"].append(
        log_agent_run(
            agent_name="obsidian",
            model=settings.get("models", {}).get("subagent", "claude-haiku-4-5"),
            usage=usage,
            duration=0.0,
            output={
                "notes_updated": task_result["knowledge_updates"],
                "task_file_written": task_file_path,
                "digest_updated": digest_path,
            },
            errors=[],
        )
    )

    lesson_files = _build_lesson_files(task_result, vault_settings.get("lessons_dir", "jarvis/agents"))
    knowledge_files = _build_knowledge_updates(task_result, vault_root)
    task_result["knowledge_updates"] = [
        task_file_path,
        *(item["vault_path"] for item in lesson_files),
        *(item["vault_path"] for item in knowledge_files),
    ]
    task_markdown = _build_task_record(task_result, task or {})
    digest_markdown = _build_digest(task_result)
    outputs = [
        {
            "vault_path": task_file_path,
            "content": task_markdown,
        },
        {
            "vault_path": digest_path,
            "content": digest_markdown,
        },
        *lesson_files,
        *knowledge_files,
    ]
    return outputs


def _build_task_record(task_result: dict[str, Any], task: dict[str, Any]) -> str:
    request_text = sanitize_text(task.get("request", task_result.get("task", {}).get("request", "")))
    total_input = sum(run["input_tokens"] for run in task_result["agents_executed"])
    total_output = sum(run["output_tokens"] for run in task_result["agents_executed"])
    total_duration = sum(run["duration_seconds"] for run in task_result["agents_executed"])
    estimated_cost = calculate_cost(task_result["agents_executed"])
    draft_section = _format_drafts(task_result["draft_communications"])
    knowledge_updates = task_result.get("knowledge_updates", [])
    knowledge_lines = "\n".join(f"- {path}" for path in knowledge_updates) if knowledge_updates else "- (none)"
    rows = [
        f"| {run['agent_name']} | {run['model']} | {run['input_tokens']} | {run['output_tokens']} | {run['duration_seconds']:.1f}s |"
        for run in task_result["agents_executed"]
    ]
    rows.append(f"| **Total** |  | **{total_input}** | **{total_output}** | **{total_duration:.1f}s** |")
    return "\n".join(
        [
            f"# Task: {sanitize_text(task_result['task_title'])}",
            "",
            f"**Task ID**: {task_result['task_id']}",
            f"**Run**: {task_result['run_timestamp']}",
            f"**Mode**: {task_result['mode']}",
            f"**Status**: {task_result['status']}",
            "",
            "## Request",
            "",
            request_text or "Request withheld.",
            "",
            "## Output",
            "",
            sanitize_text(task_result["output_summary"]),
            "",
            "## Token Usage",
            "",
            "| Agent | Model | Input | Output | Duration |",
            "|-------|-------|-------|--------|----------|",
            *rows,
            "",
            f"**Estimated cost**: ${estimated_cost:.2f}",
            "",
            "## Knowledge Updates",
            "",
            knowledge_lines,
            "",
            "## Draft Communications",
            "",
            draft_section,
        ]
    )


def _build_digest(task_result: dict[str, Any]) -> str:
    total_input = sum(run["input_tokens"] for run in task_result["agents_executed"])
    total_output = sum(run["output_tokens"] for run in task_result["agents_executed"])
    estimated_cost = calculate_cost(task_result["agents_executed"])
    drafts = task_result["draft_communications"]
    draft_lines = [f"- {draft['channel']}: pending approval" for draft in drafts] or ["- (none)"]
    open_questions = [f"- {item}" for item in task_result["clarifications_needed"]] or ["- (none)"]
    knowledge_lines = [f"- {path}" for path in task_result.get("knowledge_updates", [])] or ["- (none)"]
    learning_lines = [f"- {run['agent_name']}: completed" for run in task_result["agents_executed"]] or ["- (none)"]
    return "\n".join(
        [
            f"# Nightly Digest: {_today_string()}",
            "",
            "## Tasks Completed",
            "",
            f"- {task_result['task_id']} — {sanitize_text(task_result['task_title'])}",
            "",
            "## Usage",
            "",
            f"- Input tokens: {total_input}",
            f"- Output tokens: {total_output}",
            f"- Estimated cost: ${estimated_cost:.2f}",
            "",
            "## Knowledge Notes Updated",
            "",
            *knowledge_lines,
            "",
            "## Key Learnings",
            "",
            *learning_lines,
            "",
            "## Draft Communications",
            "",
            *draft_lines,
            "",
            "## Open Questions",
            "",
            *open_questions,
        ]
    )


def _build_empty_digest() -> str:
    return "\n".join(
        [
            f"# Nightly Digest: {_today_string()}",
            "",
            "## Tasks Completed",
            "",
            "No tasks assigned today.",
        ]
    )


def _build_lesson_files(task_result: dict[str, Any], lessons_dir: str) -> list[dict[str, str]]:
    outputs: list[dict[str, str]] = []
    run_date = task_result["run_timestamp"][:10]
    for run in task_result["agents_executed"]:
        content = "\n".join(
            [
                f"## {run_date} — {task_result['task_id']}",
                f"- What failed: {'; '.join(run['errors']) if run['errors'] else 'nothing'}",
                f"- What worked: {sanitize_text(task_result['output_summary'])}",
                "- Pattern discovered: Sequential task handoff remains stable.",
                "- Tokens saved: 0",
                "",
            ]
        )
        outputs.append({"vault_path": f"{lessons_dir}/{run['agent_name']}-lessons.md", "content": content})
    return outputs


def _build_knowledge_updates(task_result: dict[str, Any], vault_root: str) -> list[dict[str, str]]:
    outputs: list[dict[str, str]] = []
    for path in task_result.get("knowledge_updates", []):
        current = read_note(path, vault_root) if note_exists(path, vault_root) else ""
        updated = "\n".join(
            [
                current.strip(),
                f"## Update from {task_result['task_id']}",
                sanitize_text(task_result["output_summary"]),
            ]
        ).strip()
        outputs.append({"vault_path": path, "content": updated + "\n"})
    return outputs


def _stage_draft_communications(task_result: dict[str, Any], task: dict[str, Any]) -> list[dict[str, str]]:
    drafts: list[dict[str, str]] = []
    request_text = sanitize_text(task.get("request", task_result.get("task", {}).get("request", "")))
    lowered_request = request_text.lower()
    if "draft a teams message" in lowered_request or "teams message" in lowered_request:
        drafts.append(
            {
                "draft_id": str(uuid4()),
                "task_id": task_result["task_id"],
                "channel": "teams",
                "recipient": "Aprilia team",
                "subject": sanitize_text(task_result["task_title"]),
                "body": "[HUMAN APPROVAL REQUIRED]\nThe work is complete and the team can request follow-up help at any time.",
                "approval_status": "pending",
                "flag": "[HUMAN APPROVAL REQUIRED]",
            }
        )
    elif "draft an email" in lowered_request or "email" in lowered_request:
        drafts.append(
            {
                "draft_id": str(uuid4()),
                "task_id": task_result["task_id"],
                "channel": "email",
                "recipient": "Operator-reviewed recipient",
                "subject": sanitize_text(task_result["task_title"]),
                "body": "[HUMAN APPROVAL REQUIRED]\nDraft email content requires operator review before sending.",
                "approval_status": "pending",
                "flag": "[HUMAN APPROVAL REQUIRED]",
            }
        )
    draft_keywords = ("email", "teams", "send", "notify", "message to")
    for run in task_result["agents_executed"]:
        candidate_text = sanitize_text(str(run.get("output", "")))
        lowered = candidate_text.lower()
        if not any(keyword in lowered for keyword in draft_keywords):
            continue
        channel = "teams" if "teams" in lowered else "email"
        if drafts and drafts[0]["channel"] == channel:
            continue
        drafts.append(
            {
                "draft_id": str(uuid4()),
                "task_id": task_result["task_id"],
                "channel": channel,
                "recipient": "Operator-reviewed recipient",
                "subject": sanitize_text(task_result["task_title"]),
                "body": f"[HUMAN APPROVAL REQUIRED]\n{candidate_text}",
                "approval_status": "pending",
                "flag": "[HUMAN APPROVAL REQUIRED]",
            }
        )
    return drafts


def _format_drafts(drafts: list[dict[str, str]]) -> str:
    if not drafts:
        return "_(none)_"
    lines: list[str] = []
    for draft in drafts:
        lines.extend(
            [
                f"### {draft['channel'].title()} Draft",
                "",
                draft["body"],
                "",
            ]
        )
    return "\n".join(lines).strip()


def _today_string() -> str:
    return datetime.now(timezone.utc).date().isoformat()
