"""Persisted usage history for weekly cost rollups."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orchestrator.utils.token_logger import calculate_cost


USAGE_HISTORY_PATH = "jarvis/usage-history.json"


def build_usage_entry(task_result: dict[str, Any]) -> dict[str, Any]:
    input_tokens = sum(run["input_tokens"] for run in task_result["agents_executed"])
    output_tokens = sum(run["output_tokens"] for run in task_result["agents_executed"])
    return {
        "task_id": task_result["task_id"],
        "run_timestamp": task_result["run_timestamp"],
        "status": task_result["status"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": calculate_cost(task_result["agents_executed"]),
    }


def load_usage_history(root: str | Path, history_path: str = USAGE_HISTORY_PATH) -> list[dict[str, Any]]:
    path = Path(root) / history_path
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def append_usage_history(
    root: str | Path,
    task_result: dict[str, Any],
    history_path: str = USAGE_HISTORY_PATH,
) -> None:
    path = Path(root) / history_path
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = load_usage_history(root, history_path)
    current = build_usage_entry(task_result)
    key = _entry_key(current)
    filtered = [entry for entry in entries if _entry_key(entry) != key]
    filtered.append(current)
    path.write_text(json.dumps(filtered, indent=2) + "\n", encoding="utf-8")


def _entry_key(entry: dict[str, Any]) -> tuple[str, str]:
    return (str(entry.get("task_id", "")), str(entry.get("run_timestamp", "")))
