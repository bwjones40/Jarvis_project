"""Structured JSON run logging for Jarvis executions."""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass
class RunContext:
    run_id: str
    trace_id: str
    log_path: Path


def start_run(workflow_id: str, trigger_source: str, task_id: str | None = None) -> RunContext:
    run_id = str(uuid4())
    trace_id = str(uuid4())
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = Path(f"jarvis/logs/{date_str}/{run_id}.json")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    run_obj = {
        "run": {
            "run_id": run_id,
            "trace_id": trace_id,
            "workflow_id": workflow_id,
            "trigger_source": trigger_source,
            "task_id": task_id,
            "started_at": _utc_now(),
            "completed_at": None,
            "overall_status": "running",
        },
        "agents": [],
    }
    log_path.write_text(json.dumps(run_obj, indent=2), encoding="utf-8")
    return RunContext(run_id=run_id, trace_id=trace_id, log_path=log_path)


def log_agent_entry(run_context: RunContext, entry: dict) -> None:
    try:
        data = json.loads(run_context.log_path.read_text(encoding="utf-8"))
        data["agents"].append(entry)
        run_context.log_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        warnings.warn(f"run_logger: could not append entry — {exc}")


def finalize_run(run_context: RunContext, overall_status: str) -> None:
    try:
        data = json.loads(run_context.log_path.read_text(encoding="utf-8"))
        data["run"]["completed_at"] = _utc_now()
        data["run"]["overall_status"] = overall_status
        run_context.log_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        warnings.warn(f"run_logger: could not finalize run — {exc}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
