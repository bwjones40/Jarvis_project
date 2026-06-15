"""Jarvis entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml

from orchestrator.agents.obsidian_writer import build_vault_outputs
from orchestrator.agents.gcp_discovery import run_gcp_discovery
from orchestrator.agents.orchestrator import run_orchestrator
from orchestrator.agents.research import run_research
from orchestrator.utils.inbox_parser import InboxParseError, parse_inbox
from orchestrator.utils.power_automate import post_files
from orchestrator.utils.usage_history import append_usage_history
from orchestrator.utils.vault_reader import search_notes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jarvis orchestrator entry point")
    parser.add_argument("--mode", choices=["overnight", "daytime"], default=None)
    parser.add_argument("--task", help="Run a one-off daytime task without reading jarvis/inbox.md.")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls and webhook posting.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    settings = load_settings(repo_root / "config" / "settings.yaml")
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
    notes = search_notes(task["request"], vault_root, max_results=settings.get("research", {}).get("max_context_notes", 3))
    task_result = run_orchestrator(task, notes, settings)
    if "research" in task_result["routing"]["agents_to_run"]:
        task_result = run_research(task_result, settings, vault_root)
    if "gcp" in task_result["routing"]["agents_to_run"]:
        task_result = run_gcp_discovery(task_result, settings)

    outputs = build_vault_outputs(task_result=task_result, task=task, settings=settings, vault_root=str(repo_root))
    posted = _maybe_post_outputs(outputs)
    if posted and not args.task:
        append_usage_history(repo_root, task_result)
        (repo_root / "jarvis" / "inbox.md").write_text(_inbox_template(), encoding="utf-8")
    print(json.dumps(task_result, indent=2))
    return 0


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


def _maybe_post_outputs(outputs: list[dict[str, str]]) -> bool:
    webhook_url = os.getenv("POWER_AUTOMATE_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return False
    run_metadata = {
        "task_id": outputs[0]["vault_path"].replace("/", "-"),
        "run_timestamp": outputs[0]["content"].splitlines()[0] if outputs and outputs[0]["content"] else "",
        "total_files": len(outputs),
    }
    return post_files(outputs, run_metadata, webhook_url)


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
