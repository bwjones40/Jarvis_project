"""Jarvis entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml

from orchestrator.agents import gcp_discovery as gcp_discovery_agent
from orchestrator.agents import obsidian_writer as obsidian_writer_agent
from orchestrator.agents import orchestrator as orchestrator_agent
from orchestrator.agents import research as research_agent
from orchestrator.agents import stats_reporter
from orchestrator.agents import validation as validation_agent
from orchestrator.agents.obsidian_writer import build_vault_outputs
from orchestrator.agents.gcp_discovery import run_gcp_discovery
from orchestrator.agents.orchestrator import run_orchestrator
from orchestrator.agents.research import run_research
from orchestrator.utils.inbox_parser import InboxParseError, parse_inbox
from orchestrator.utils.power_automate import post_files
from orchestrator.utils.run_logger import RunContext
from orchestrator.utils import run_logger
from orchestrator.utils.token_logger import calculate_cost
from orchestrator.utils.usage_history import append_usage_history
from orchestrator.utils.vault_reader import search_notes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jarvis orchestrator entry point")
    parser.add_argument("--mode", choices=["overnight", "daytime", "stats_report"], default=None)
    parser.add_argument("--task", help="Run a one-off daytime task without reading jarvis/inbox.md.")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls and webhook posting.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    settings = load_settings(repo_root / "config" / "settings.yaml")
    if args.mode == "stats_report":
        logging_settings = settings.get("logging", {})
        stats_dir_rel = logging_settings.get("stats_dir", "jarvis/ci")
        stats_reporter.run_stats_report(
            log_dir=str(repo_root / logging_settings.get("log_dir", "jarvis/logs")),
            stats_dir=str(repo_root / stats_dir_rel),
            vault_dir=stats_dir_rel,
            webhook_url=os.getenv("POWER_AUTOMATE_WEBHOOK_URL", "").strip() or None,
        )
        return 0
    if args.task:
        task = _build_direct_task(args.task, args.mode or "daytime")
    else:
        inbox_path = repo_root / "jarvis" / "inbox.md"
        if not inbox_path.exists():
            print("Inbox file not found: jarvis/inbox.md")
            return 1

        try:
            task = parse_inbox(inbox_path)
        except InboxParseError as exc:
            print(f"Failed to parse inbox: {exc}")
            return 1

    if task is None:
        if args.dry_run:
            print("No task in inbox")
            return 0
        outputs = build_vault_outputs(task_result=None, task=None, settings=settings, vault_root=str(repo_root))
        _maybe_post_outputs(outputs)
        print("No task in inbox")
        return 0

    task["mode"] = args.mode or task["mode"]
    if args.dry_run:
        print(json.dumps(task, indent=2))
        return 0

    vault_root = str(repo_root / settings.get("vault", {}).get("root", "jarvis"))
    predicted_task_id = orchestrator_agent._build_task_id(task["title"])
    run_ctx = run_logger.start_run(
        workflow_id="jarvis",
        trigger_source=_detect_trigger_source(),
        task_id=predicted_task_id,
    )
    overall_status = "failed"
    task_result: dict[str, Any] | None = None

    try:
        notes = search_notes(task["request"], vault_root, max_results=settings.get("research", {}).get("max_context_notes", 3))
        task_result = run_orchestrator(task, notes, settings)
        _log_latest_agent(run_ctx, task_result, task)

        if "research" in task_result["routing"]["agents_to_run"]:
            task_result = run_research(task_result, settings, vault_root)
            task_result = _validate_agent_with_retry(
                task_result=task_result,
                task=task,
                settings=settings,
                run_ctx=run_ctx,
                agent_name="research",
                rerun=lambda current: run_research(current, settings, vault_root),
            )
            _log_latest_agent(run_ctx, task_result, task)
        if "gcp" in task_result["routing"]["agents_to_run"]:
            task_result = run_gcp_discovery(task_result, settings)
            _log_latest_agent(run_ctx, task_result, task)

        outputs = build_vault_outputs(task_result=task_result, task=task, settings=settings, vault_root=str(repo_root))
        task_result, outputs = _validate_obsidian_with_retry(
            task_result=task_result,
            task=task,
            settings=settings,
            run_ctx=run_ctx,
            repo_root=str(repo_root),
            outputs=outputs,
        )
        _log_latest_agent(run_ctx, task_result, task)
        overall_status = task_result.get("status", "completed")
        run_logger.finalize_run(run_ctx, overall_status)
        posted = _maybe_post_outputs(outputs + [run_ctx.log_path], task_result=task_result)
        if posted:
            append_usage_history(repo_root, task_result)
            if not args.task:
                (repo_root / "jarvis" / "inbox.md").write_text(_inbox_template(), encoding="utf-8")
        print(json.dumps(task_result, indent=2))
        return 0
    except Exception:
        run_logger.finalize_run(run_ctx, overall_status)
        raise


def load_settings(settings_path: Path) -> dict[str, Any]:
    if not settings_path.exists():
        return {}
    data = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _build_direct_task(request: str, mode: str) -> dict[str, Any]:
    return {
        "title": "Daytime GCP discovery",
        "priority": "medium",
        "mode": mode,
        "agents_needed": ["orchestrator", "gcp", "obsidian"],
        "due": "manual run",
        "request": request,
        "context": "",
        "copilot_handoff": "",
    }


def _maybe_post_outputs(outputs: list[dict[str, str] | str | Path], task_result: dict[str, Any] | None = None) -> bool:
    webhook_url = os.getenv("POWER_AUTOMATE_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return False
    run_metadata = {
        "task_id": task_result.get("task_id") if task_result else "no-task",
        "run_timestamp": task_result.get("run_timestamp", "") if task_result else "",
        "total_files": len(outputs),
    }
    return post_files(outputs, run_metadata, webhook_url)


def _detect_trigger_source() -> str:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        event = os.environ.get("GITHUB_EVENT_NAME", "unknown")
        if event == "schedule":
            return "github_actions_cron"
        if event == "push":
            return "inbox_push"
        return "workflow_dispatch"
    return "local"


def _log_latest_agent(run_ctx: RunContext, task_result: dict[str, Any], task: dict[str, Any]) -> None:
    if not task_result.get("agents_executed"):
        return
    run = task_result["agents_executed"][-1]
    agent_name = _normalize_agent_name(run.get("agent_name", ""))
    entry = {
        "timestamp": _utc_now(),
        "run_id": run_ctx.run_id,
        "trace_id": run_ctx.trace_id,
        "agent_name": agent_name,
        "agent_version": _agent_version(agent_name),
        "status": _agent_status(agent_name, run, task_result),
        "latency_ms": int(round(float(run.get("duration_seconds", 0.0)) * 1000)),
        "token_usage": {
            "input": int(run.get("input_tokens", 0) or 0),
            "output": int(run.get("output_tokens", 0) or 0),
            "total": int(run.get("input_tokens", 0) or 0) + int(run.get("output_tokens", 0) or 0),
            "estimated_cost_usd": calculate_cost([run]),
        },
        "input_summary": _truncate_summary(_build_input_summary(agent_name, task_result, task)),
        "output_summary": _truncate_summary(_build_output_summary(run)),
    }
    for key in ("confidence_score", "validation_pass", "retry_count", "skip_reason", "escalation_flag", "human_review_required", "partial_run"):
        if key in run:
            entry[key] = run[key]
    if run.get("escalation_flag"):
        entry["error_type"] = "validation_fail"
    run_logger.log_agent_entry(run_ctx, entry)


def _normalize_agent_name(agent_name: str) -> str:
    if agent_name == "obsidian":
        return "obsidian_writer"
    if agent_name == "gcp":
        return "gcp_discovery"
    return agent_name


def _validation_thresholds(settings: dict[str, Any]) -> dict[str, float]:
    validation_settings = settings.get("validation", {})
    return {
        "pass_threshold": float(validation_settings.get("pass_threshold", 0.90)),
        "retry_min_threshold": float(validation_settings.get("retry_min_threshold", 0.60)),
        "retry_accept_threshold": float(validation_settings.get("retry_accept_threshold", 0.80)),
        "skip_threshold": float(validation_settings.get("skip_threshold", 0.60)),
    }


def _validate_agent_with_retry(
    task_result: dict[str, Any],
    task: dict[str, Any],
    settings: dict[str, Any],
    run_ctx: RunContext,
    agent_name: str,
    rerun: Any,
) -> dict[str, Any]:
    thresholds = _validation_thresholds(settings)
    result = validation_agent.score_output(agent_name, task_result["agents_executed"][-1]["output"], {"task": task, "task_result": task_result}, run_ctx.run_id, thresholds)
    if result.pass_:
        _apply_validation_fields(task_result["agents_executed"][-1], result, retry_count=0)
        return task_result

    if result.retry_recommended:
        task_result["agents_executed"].pop()
        task_result = rerun(task_result)
        retry_result = validation_agent.score_output(agent_name, task_result["agents_executed"][-1]["output"], {"task": task, "task_result": task_result}, run_ctx.run_id, thresholds)
        if retry_result.confidence_score >= thresholds["retry_accept_threshold"]:
            _apply_validation_fields(task_result["agents_executed"][-1], retry_result, retry_count=1)
            return task_result
        _apply_validation_fields(
            task_result["agents_executed"][-1],
            retry_result,
            retry_count=1,
            skip_reason="validation_score_below_retry_accept_threshold",
            escalation_flag=True,
            human_review_required=True,
            partial_run=True,
        )
        _mark_human_review(task_result, agent_name, "validation score remained below retry accept threshold")
        return task_result

    _apply_validation_fields(
        task_result["agents_executed"][-1],
        result,
        retry_count=0,
        skip_reason="validation_score_below_skip_threshold",
        escalation_flag=True,
        human_review_required=True,
        partial_run=True,
    )
    _mark_human_review(task_result, agent_name, "validation score below skip threshold")
    return task_result


def _validate_obsidian_with_retry(
    task_result: dict[str, Any],
    task: dict[str, Any],
    settings: dict[str, Any],
    run_ctx: RunContext,
    repo_root: str,
    outputs: list[dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    thresholds = _validation_thresholds(settings)
    result = validation_agent.score_output("obsidian_writer", task_result["agents_executed"][-1]["output"], {"task": task, "task_result": task_result}, run_ctx.run_id, thresholds)
    if result.pass_:
        _apply_validation_fields(task_result["agents_executed"][-1], result, retry_count=0)
        return task_result, _refresh_digest_output(outputs, task_result, settings, repo_root)

    if result.retry_recommended:
        task_result["agents_executed"].pop()
        outputs = _rerun_obsidian(task_result, task, settings, repo_root)
        retry_result = validation_agent.score_output("obsidian_writer", task_result["agents_executed"][-1]["output"], {"task": task, "task_result": task_result}, run_ctx.run_id, thresholds)
        if retry_result.confidence_score >= thresholds["retry_accept_threshold"]:
            _apply_validation_fields(task_result["agents_executed"][-1], retry_result, retry_count=1)
            return task_result, _refresh_digest_output(outputs, task_result, settings, repo_root)
        _apply_validation_fields(
            task_result["agents_executed"][-1],
            retry_result,
            retry_count=1,
            skip_reason="validation_score_below_retry_accept_threshold",
            escalation_flag=True,
            human_review_required=True,
            partial_run=True,
        )
        _mark_human_review(task_result, "obsidian_writer", "validation score remained below retry accept threshold")
        return task_result, _refresh_digest_output(outputs, task_result, settings, repo_root)

    _apply_validation_fields(
        task_result["agents_executed"][-1],
        result,
        retry_count=0,
        skip_reason="validation_score_below_skip_threshold",
        escalation_flag=True,
        human_review_required=True,
        partial_run=True,
    )
    _mark_human_review(task_result, "obsidian_writer", "validation score below skip threshold")
    return task_result, _refresh_digest_output(outputs, task_result, settings, repo_root)


def _rerun_obsidian(task_result: dict[str, Any], task: dict[str, Any], settings: dict[str, Any], repo_root: str) -> list[dict[str, str]]:
    return build_vault_outputs(task_result=task_result, task=task, settings=settings, vault_root=repo_root)


def _refresh_digest_output(
    outputs: list[dict[str, str]],
    task_result: dict[str, Any],
    settings: dict[str, Any],
    repo_root: str,
) -> list[dict[str, str]]:
    tasks_dir = settings.get("vault", {}).get("tasks_dir", "jarvis/tasks")
    pii_mode = settings.get("pii", {}).get("mode", "strict")
    digest_content = obsidian_writer_agent._build_digest(
        task_result,
        vault_root=repo_root,
        tasks_dir=tasks_dir,
        pii_mode=pii_mode,
    )
    refreshed: list[dict[str, str]] = []
    for item in outputs:
        if item.get("vault_path", "").startswith(settings.get("vault", {}).get("digests_dir", "jarvis/digests")):
            refreshed.append({"vault_path": item["vault_path"], "content": digest_content})
        else:
            refreshed.append(item)
    return refreshed


def _apply_validation_fields(
    agent_run: dict[str, Any],
    result: validation_agent.ValidationResult,
    retry_count: int,
    skip_reason: str | None = None,
    escalation_flag: bool | None = None,
    human_review_required: bool | None = None,
    partial_run: bool | None = None,
) -> None:
    effective_escalation = bool(escalation_flag) if escalation_flag is not None else result.escalate
    effective_human_review = bool(human_review_required) if human_review_required is not None else result.escalate
    effective_partial = bool(partial_run) if partial_run is not None else False
    agent_run["confidence_score"] = result.confidence_score
    agent_run["validation_pass"] = result.pass_ or (retry_count > 0 and not effective_escalation and skip_reason is None)
    agent_run["retry_count"] = retry_count
    agent_run["skip_reason"] = skip_reason
    agent_run["escalation_flag"] = effective_escalation
    agent_run["human_review_required"] = effective_human_review
    agent_run["partial_run"] = effective_partial


def _mark_human_review(task_result: dict[str, Any], agent_name: str, reason: str) -> None:
    task_result["status"] = "partial"
    message = f"[HUMAN REVIEW REQUIRED] {agent_name}: {reason}"
    if message not in task_result["clarifications_needed"]:
        task_result["clarifications_needed"].append(message)


def _agent_version(agent_name: str) -> str:
    versions = {
        "orchestrator": orchestrator_agent.agent_version,
        "research": research_agent.agent_version,
        "gcp_discovery": gcp_discovery_agent.agent_version,
        "obsidian_writer": obsidian_writer_agent.agent_version,
    }
    return versions.get(agent_name, "1.0.0")


def _agent_status(agent_name: str, run: dict[str, Any], task_result: dict[str, Any]) -> str:
    if run.get("errors"):
        return "partial"
    if agent_name == "gcp_discovery":
        summary = json.dumps(run.get("output", {}))
        if "skipped" in summary.lower():
            return "skipped"
    if agent_name == "orchestrator" and task_result.get("status") == "needs_clarification":
        return "partial"
    return "success"


def _build_input_summary(agent_name: str, task_result: dict[str, Any], task: dict[str, Any]) -> str:
    request = str(task.get("request", ""))
    if agent_name == "research":
        return f"Task: {request}. Retrieved {len(task_result.get('research_sources', []))} vault notes."
    if agent_name == "obsidian_writer":
        return f"TaskResult with {max(len(task_result.get('agents_executed', [])) - 1, 0)} prior agent runs."
    return f"Task: {request}"


def _build_output_summary(run: dict[str, Any]) -> str:
    output = run.get("output", {})
    if isinstance(output, dict):
        if "context_summary" in output:
            return f"{len(str(output['context_summary']).split())} words. Cache hit: {output.get('cache_hit', False)}."
        if "plain_english_summary" in output:
            return str(output["plain_english_summary"])
        if "digest_updated" in output:
            return f"Wrote task record and digest. Notes updated: {len(output.get('notes_updated', []))}."
        if "plan" in output:
            return str(output["plan"])
    return str(output)


def _truncate_summary(value: str) -> str:
    text = " ".join(str(value).split())
    return text[:200]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _inbox_template() -> str:
    return "\n".join(
        [
            "# Jarvis Inbox",
            "",
            "## Task: Replace this title before commit",
            "**Priority**: medium",
            "**Mode**: overnight",
            "**Agents needed**: orchestrator, research, obsidian",
            "**Due**: next run",
            "",
            "### Request",
            "Describe the task Jarvis should complete before the next run.",
            "",
            "### Context",
            "Optional project context, links, or non-PII background.",
            "",
            "### Copilot handoff",
            "Optional manual handoff instructions for Copilot.",
            "",
            "---",
            "_Clear this file after each run. Jarvis archives completed tasks to jarvis/tasks/_",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
