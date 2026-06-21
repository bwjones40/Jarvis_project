"""Build vault-ready markdown outputs from task results."""

from __future__ import annotations

import json
import os
import re
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import sleep
from typing import Any
from uuid import uuid4

try:
    import anthropic
except ModuleNotFoundError:  # pragma: no cover - local fallback when dependency is absent
    anthropic = None

from orchestrator.utils.pii_guard import get_pii_mode, sanitize_text
from orchestrator.utils.token_logger import calculate_cost, log_agent_run
from orchestrator.utils.usage_history import build_usage_entry, load_usage_history
from orchestrator.utils.vault_reader import note_exists, read_note

agent_version = "1.0.0"

OBSIDIAN_WRITER_PROMPT = Path("prompts/obsidian_writer.md").read_text(encoding="utf-8")
client = anthropic.Anthropic() if anthropic is not None and os.getenv("ANTHROPIC_API_KEY", "").strip() else None


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

    pii_mode = get_pii_mode(settings)
    task_result["draft_communications"] = _stage_draft_communications(task_result, task or {}, pii_mode)
    task_file_path = f"{vault_settings.get('tasks_dir', 'jarvis/tasks')}/{task_result['task_id']}.md"
    generated_markdown, usage = _generate_llm_markdown(
        task_result=task_result,
        task=task or {},
        settings=settings,
        vault_root=vault_root,
        task_file_path=task_file_path,
        digest_path=digest_path,
    )
    task_result["agents_executed"].append(
        log_agent_run(
            agent_name="obsidian",
            model=settings.get("models", {}).get("orchestrator", "claude-sonnet-4-6"),
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

    lesson_files = _build_lesson_files(task_result, vault_settings.get("lessons_dir", "jarvis/agents"), vault_root, pii_mode)
    knowledge_files = _build_knowledge_updates(task_result, vault_root, pii_mode)
    task_result["knowledge_updates"] = [
        task_file_path,
        *(item["vault_path"] for item in lesson_files),
        *(item["vault_path"] for item in knowledge_files),
    ]
    task_markdown = generated_markdown.get("task_record_markdown") if generated_markdown else None
    digest_markdown = generated_markdown.get("digest_markdown") if generated_markdown else None
    if not task_markdown:
        task_markdown = _build_task_record(task_result, task or {}, pii_mode)
    if not digest_markdown:
        digest_markdown = _build_digest(
            task_result,
            vault_root=vault_root,
            tasks_dir=vault_settings.get("tasks_dir", "jarvis/tasks"),
            pii_mode=pii_mode,
        )
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


def _build_task_record(task_result: dict[str, Any], task: dict[str, Any], pii_mode: str) -> str:
    request_text = sanitize_text(task.get("request", task_result.get("task", {}).get("request", "")), mode=pii_mode)
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
            f"# Task: {sanitize_text(task_result['task_title'], mode=pii_mode)}",
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
            sanitize_text(task_result.get("research_summary") or task_result["output_summary"], mode=pii_mode),
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


def _build_digest(task_result: dict[str, Any], vault_root: str, tasks_dir: str, pii_mode: str) -> str:
    total_input = sum(run["input_tokens"] for run in task_result["agents_executed"])
    total_output = sum(run["output_tokens"] for run in task_result["agents_executed"])
    estimated_cost = calculate_cost(task_result["agents_executed"])
    weekly_rollup = _build_weekly_rollup(task_result, vault_root, tasks_dir)
    drafts = task_result["draft_communications"]
    draft_lines = [f"- {draft['channel']}: pending approval" for draft in drafts] or ["- (none)"]
    open_questions = [f"- {item}" for item in task_result["clarifications_needed"]] or ["- (none)"]
    knowledge_lines = [f"- {path}" for path in task_result.get("knowledge_updates", [])] or ["- (none)"]
    learning_lines = [f"- {run['agent_name']}: completed" for run in task_result["agents_executed"]] or ["- (none)"]
    quality_rows = _build_quality_rows(task_result["agents_executed"])
    completed_lines = (
        [f"- {task_result['task_id']} — {sanitize_text(task_result['task_title'], mode=pii_mode)}"]
        if task_result["status"] == "completed"
        else ["- (none)"]
    )
    attention_lines = (
        [f"- {task_result['task_id']} — {sanitize_text(task_result['task_title'], mode=pii_mode)} ({task_result['status']})"]
        if task_result["status"] != "completed"
        else ["- (none)"]
    )
    return "\n".join(
        [
            f"# Nightly Digest: {_today_string()}",
            "",
            "## Tasks Completed",
            "",
            *completed_lines,
            "",
            "## Tasks Requiring Attention",
            "",
            *attention_lines,
            "",
            "## Usage",
            "",
            f"- Input tokens: {total_input}",
            f"- Output tokens: {total_output}",
            f"- Estimated cost: ${estimated_cost:.2f}",
            "",
            "## Weekly Cost Rollup",
            "",
            f"- Last 7 days estimated cost: ${weekly_rollup['estimated_cost']:.2f}",
            f"- Last 7 days input tokens: {weekly_rollup['input_tokens']}",
            f"- Last 7 days output tokens: {weekly_rollup['output_tokens']}",
            f"- Task records counted: {weekly_rollup['task_count']}",
            "",
            "## Knowledge Notes Updated",
            "",
            *knowledge_lines,
            "",
            "## Run Quality Summary",
            "",
            "| Agent | Confidence | Validation | Retry Count | Escalation |",
            "|-------|------------|------------|-------------|------------|",
            *quality_rows,
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


def _build_weekly_rollup(task_result: dict[str, Any], vault_root: str, tasks_dir: str) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=6)
    entries: dict[tuple[str, str], dict[str, Any]] = {}

    current_entry = build_usage_entry(task_result)
    entries[_rollup_key(current_entry)] = current_entry

    for entry in load_usage_history(vault_root):
        run_date = _entry_run_date(entry)
        if run_date is None or run_date < cutoff:
            continue
        entries[_rollup_key(entry)] = entry

    root = Path(vault_root)
    tasks_path = root / tasks_dir if not Path(tasks_dir).is_absolute() else Path(tasks_dir)
    if tasks_path.exists():
        for path in tasks_path.glob("task-*.md"):
            content = path.read_text(encoding="utf-8")
            run_date = _extract_run_date(content)
            if run_date is None or run_date < cutoff:
                continue
            totals = _extract_token_totals(content)
            entry = {
                "task_id": path.stem,
                "run_timestamp": run_date.isoformat(),
                "input_tokens": totals["input_tokens"],
                "output_tokens": totals["output_tokens"],
                "estimated_cost": _extract_estimated_cost(content),
            }
            entries[_rollup_key(entry)] = entry

    input_tokens = sum(int(entry.get("input_tokens", 0) or 0) for entry in entries.values())
    output_tokens = sum(int(entry.get("output_tokens", 0) or 0) for entry in entries.values())
    estimated_cost = sum(float(entry.get("estimated_cost", 0.0) or 0.0) for entry in entries.values())

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": estimated_cost,
        "task_count": len(entries),
    }


def _rollup_key(entry: dict[str, Any]) -> tuple[str, str]:
    return (str(entry.get("task_id", "")), str(entry.get("run_timestamp", ""))[:10])


def _entry_run_date(entry: dict[str, Any]) -> Any:
    run_timestamp = str(entry.get("run_timestamp", ""))
    if len(run_timestamp) < 10:
        return None
    try:
        return datetime.fromisoformat(run_timestamp[:10]).date()
    except ValueError:
        return None


def _extract_run_date(content: str) -> Any:
    match = re.search(r"^\*\*Run\*\*:\s*(\d{4}-\d{2}-\d{2})", content, flags=re.MULTILINE)
    if not match:
        return None
    return datetime.fromisoformat(match.group(1)).date()


def _extract_token_totals(content: str) -> dict[str, int]:
    match = re.search(r"\| \*\*Total\*\* \|  \| \*\*(\d+)\*\* \| \*\*(\d+)\*\*", content)
    if not match:
        return {"input_tokens": 0, "output_tokens": 0}
    return {"input_tokens": int(match.group(1)), "output_tokens": int(match.group(2))}


def _extract_estimated_cost(content: str) -> float:
    match = re.search(r"\*\*Estimated cost\*\*:\s*\$(\d+(?:\.\d+)?)", content)
    return float(match.group(1)) if match else 0.0


def _build_lesson_files(task_result: dict[str, Any], lessons_dir: str, vault_root: str, pii_mode: str) -> list[dict[str, str]]:
    outputs: list[dict[str, str]] = []
    run_date = task_result["run_timestamp"][:10]
    for run in task_result["agents_executed"]:
        vault_path = f"{lessons_dir}/{run['agent_name']}-lessons.md"
        current = read_note(vault_path, vault_root).rstrip() if note_exists(vault_path, vault_root) else ""
        entry = "\n".join(
            [
                f"## {run_date} — {task_result['task_id']}",
                f"- What failed: {'; '.join(run['errors']) if run['errors'] else 'nothing'}",
                f"- What worked: {sanitize_text(task_result['output_summary'], mode=pii_mode)}",
                "- Pattern discovered: Sequential task handoff remains stable.",
                "- Tokens saved: 0",
                "",
            ]
        )
        content = f"{current}\n\n{entry}" if current else entry
        outputs.append({"vault_path": vault_path, "content": content})
    return outputs


def _build_knowledge_updates(task_result: dict[str, Any], vault_root: str, pii_mode: str) -> list[dict[str, str]]:
    outputs: list[dict[str, str]] = []
    for path in task_result.get("knowledge_updates", []):
        current = read_note(path, vault_root) if note_exists(path, vault_root) else ""
        updated = "\n".join(
            [
                current.strip(),
                f"## Update from {task_result['task_id']}",
                sanitize_text(task_result["output_summary"], mode=pii_mode),
            ]
        ).strip()
        outputs.append({"vault_path": path, "content": updated + "\n"})
    return outputs


def _stage_draft_communications(task_result: dict[str, Any], task: dict[str, Any], pii_mode: str) -> list[dict[str, str]]:
    drafts: list[dict[str, str]] = []
    request_text = sanitize_text(task.get("request", task_result.get("task", {}).get("request", "")), mode=pii_mode)
    lowered_request = request_text.lower()
    if "draft a teams message" in lowered_request or "teams message" in lowered_request:
        drafts.append(
            {
                "draft_id": str(uuid4()),
                "task_id": task_result["task_id"],
                "channel": "teams",
                "recipient": "Aprilia team",
                "subject": sanitize_text(task_result["task_title"], mode=pii_mode),
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
                "subject": sanitize_text(task_result["task_title"], mode=pii_mode),
                "body": "[HUMAN APPROVAL REQUIRED]\nDraft email content requires operator review before sending.",
                "approval_status": "pending",
                "flag": "[HUMAN APPROVAL REQUIRED]",
            }
        )
    draft_keywords = ("email", "teams", "send", "notify", "message to")
    for run in task_result["agents_executed"]:
        candidate_text = sanitize_text(str(run.get("output", "")), mode=pii_mode)
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
                "subject": sanitize_text(task_result["task_title"], mode=pii_mode),
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


def _build_quality_rows(agent_runs: list[dict[str, Any]]) -> list[str]:
    rows: list[str] = []
    for run in agent_runs:
        score = run.get("confidence_score")
        validation_pass = run.get("validation_pass")
        retry_count = run.get("retry_count", 0)
        escalation_flag = run.get("escalation_flag", False)
        score_text = f"{float(score):.2f}" if score is not None else "N/A"
        validation_text = "PASS" if validation_pass is True else ("FAIL" if validation_pass is False else "N/A")
        rows.append(
            f"| {run.get('agent_name', '')} | {score_text} | {validation_text} | {retry_count} | {str(bool(escalation_flag))} |"
        )
    return rows or ["| (none) | N/A | N/A | 0 | False |"]


def _generate_llm_markdown(
    task_result: dict[str, Any],
    task: dict[str, Any],
    settings: dict[str, Any],
    vault_root: str,
    task_file_path: str,
    digest_path: str,
) -> tuple[dict[str, str] | None, Any]:
    empty_usage = type("Usage", (), {"input_tokens": 0, "output_tokens": 0})()
    response = _call_obsidian_writer_model(
        _build_obsidian_writer_payload(
            task_result=task_result,
            task=task,
            settings=settings,
            vault_root=vault_root,
            task_file_path=task_file_path,
            digest_path=digest_path,
        )
    )
    if response is None:
        return None, empty_usage

    content = _extract_response_text(getattr(response, "content", []))
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None, getattr(response, "usage", empty_usage)
    if not isinstance(parsed, dict):
        return None, getattr(response, "usage", empty_usage)

    task_markdown = parsed.get("task_record_markdown")
    digest_markdown = parsed.get("digest_markdown")
    if not isinstance(task_markdown, str) or not isinstance(digest_markdown, str):
        return None, getattr(response, "usage", empty_usage)
    return {"task_record_markdown": task_markdown, "digest_markdown": digest_markdown}, getattr(response, "usage", empty_usage)


def _build_obsidian_writer_payload(
    task_result: dict[str, Any],
    task: dict[str, Any],
    settings: dict[str, Any],
    vault_root: str,
    task_file_path: str,
    digest_path: str,
) -> str:
    weekly_rollup = _build_weekly_rollup(task_result, vault_root, settings.get("vault", {}).get("tasks_dir", "jarvis/tasks"))
    payload = {
        "instructions": {
            "return_json_only": True,
            "required_keys": ["task_record_markdown", "digest_markdown"],
            "task_record_requirements": [
                "Include Request, Output, Token Usage, Knowledge Updates, and Draft Communications sections.",
                "Every draft communication must remain prefixed with [HUMAN APPROVAL REQUIRED].",
            ],
            "digest_requirements": [
                "Include Tasks Completed, Tasks Requiring Attention, Usage, Weekly Cost Rollup, Knowledge Notes Updated, Key Learnings, Draft Communications, and Open Questions sections.",
                "Do not describe any auto-send capability.",
            ],
        },
        "task": {
            "title": _sanitize_for_anthropic(task.get("title", task_result.get("task_title", ""))),
            "request": _sanitize_for_anthropic(task.get("request", task_result.get("task", {}).get("request", ""))),
            "mode": task_result.get("mode"),
            "status": task_result.get("status"),
        },
        "task_result": {
            "task_id": task_result.get("task_id"),
            "task_title": _sanitize_for_anthropic(task_result.get("task_title", "")),
            "run_timestamp": task_result.get("run_timestamp"),
            "output_summary": _sanitize_for_anthropic(task_result.get("output_summary", "")),
            "clarifications_needed": [_sanitize_for_anthropic(item) for item in task_result.get("clarifications_needed", [])],
            "knowledge_updates": list(task_result.get("knowledge_updates", [])),
            "draft_communications": [
                {
                    "channel": draft.get("channel", ""),
                    "body": _sanitize_for_anthropic(draft.get("body", "")),
                }
                for draft in task_result.get("draft_communications", [])
            ],
            "agents_executed": [
                {
                    "agent_name": run.get("agent_name"),
                    "model": run.get("model"),
                    "input_tokens": run.get("input_tokens", 0),
                    "output_tokens": run.get("output_tokens", 0),
                    "duration_seconds": run.get("duration_seconds", 0.0),
                    "output": _sanitize_for_anthropic(json.dumps(run.get("output", {}), ensure_ascii=True)),
                    "errors": [_sanitize_for_anthropic(err) for err in run.get("errors", [])],
                }
                for run in task_result.get("agents_executed", [])
            ],
        },
        "weekly_rollup": weekly_rollup,
        "output_paths": {
            "task_record": task_file_path,
            "digest": digest_path,
        },
    }
    return json.dumps(payload, indent=2)


def _call_obsidian_writer_model(prompt_text: str) -> Any | None:
    """Call the writer model, degrading to ``None`` instead of raising.

    The caller treats ``None`` as a graceful fallback (a deterministic vault
    output), so a transient outage or a bad/expired API key never halts the
    pipeline. Auth/permission failures skip the retry since they will not clear.
    """
    if client is None or anthropic is None:
        return None

    def _create() -> Any:
        return client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=OBSIDIAN_WRITER_PROMPT,
            messages=[{"role": "user", "content": prompt_text}],
        )

    try:
        return _create()
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        warnings.warn(f"Obsidian writer model call failed (auth/permission); using degraded fallback: {exc}")
        return None
    except anthropic.APIError:
        sleep(10)
        try:
            return _create()
        except anthropic.APIError as exc:
            warnings.warn(f"Obsidian writer model call failed after retry; using degraded fallback: {exc}")
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


def _today_string() -> str:
    return datetime.now(timezone.utc).date().isoformat()
