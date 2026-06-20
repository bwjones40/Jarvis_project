from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from orchestrator.utils.power_automate import post_files


def run_stats_report(log_dir: str, stats_dir: str, webhook_url: str = None) -> None:
    window_start = _find_window_start(stats_dir)
    window_end = _utc_now()
    log_root = Path(log_dir)
    included_runs = 0
    entries: list[dict[str, Any]] = []

    for path in sorted(log_root.glob("*/*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            warnings.warn(f"stats_reporter: skipped malformed log {path}: {exc}")
            continue

        started_at = payload.get("run", {}).get("started_at")
        if window_start is not None and (not started_at or started_at <= window_start):
            continue

        included_runs += 1
        entries.extend(payload.get("agents", []))

    agent_stats = _aggregate_agent_stats(entries)
    stats_payload = {
        "stats_run_id": str(uuid4()),
        "run_date": window_end,
        "analysis_window_start": window_start,
        "analysis_window_end": window_end,
        "total_runs_analyzed": included_runs,
        "total_agent_executions": len(entries),
        "agent_stats": agent_stats,
    }

    stats_root = Path(stats_dir)
    stats_root.mkdir(parents=True, exist_ok=True)
    date_slug = window_end[:10]
    json_path = stats_root / f"stats_{date_slug}.json"
    markdown_path = stats_root / f"stats_{date_slug}.md"
    json_path.write_text(json.dumps(stats_payload, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown_report(stats_payload), encoding="utf-8")

    if webhook_url:
        post_files(
            [markdown_path, json_path],
            {
                "task_id": "stats-report",
                "run_timestamp": window_end,
                "total_files": 2,
            },
            webhook_url,
        )


def _find_window_start(stats_dir: str) -> str | None:
    stats_root = Path(stats_dir)
    candidates = sorted(stats_root.glob("stats_*.json"), reverse=True)
    if not candidates:
        return None
    try:
        payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        warnings.warn(f"stats_reporter: skipped malformed stats baseline {candidates[0]}: {exc}")
        return None
    return payload.get("analysis_window_end")


def _aggregate_agent_stats(entries: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault(str(entry.get("agent_name", "unknown")), []).append(entry)

    results: list[dict[str, Any]] = []
    for agent_name in sorted(grouped):
        agent_entries = grouped[agent_name]
        run_count = len(agent_entries)
        success_count = sum(1 for entry in agent_entries if entry.get("status") == "success")
        total_latency = sum(int(entry.get("latency_ms", 0) or 0) for entry in agent_entries)
        total_tokens = sum(int(entry.get("token_usage", {}).get("total", 0) or 0) for entry in agent_entries)
        total_cost = sum(float(entry.get("token_usage", {}).get("estimated_cost_usd", 0.0) or 0.0) for entry in agent_entries)
        retry_count = sum(int(entry.get("retry_count", 0) or 0) for entry in agent_entries)
        escalation_count = sum(1 for entry in agent_entries if entry.get("escalation_flag") is True)

        row = {
            "agent_name": agent_name,
            "run_count": run_count,
            "success_rate": round(success_count / run_count, 4) if run_count else 0.0,
            "avg_latency_ms": int(round(total_latency / run_count)) if run_count else 0,
            "avg_tokens_per_run": int(round(total_tokens / run_count)) if run_count else 0,
            "total_cost_usd": round(total_cost, 4),
            "retry_count": retry_count,
            "escalation_count": escalation_count,
        }

        confidence_scores = [float(entry["confidence_score"]) for entry in agent_entries if entry.get("confidence_score") is not None]
        if confidence_scores:
            row["avg_confidence_score"] = round(sum(confidence_scores) / len(confidence_scores), 4)

        results.append(row)
    return results


def _build_markdown_report(stats_payload: dict[str, Any]) -> str:
    rows: list[str] = []
    for item in stats_payload.get("agent_stats", []):
        confidence = item.get("avg_confidence_score")
        confidence_text = f"{confidence:.2f}" if confidence is not None else "N/A"
        rows.append(
            f"| {item['agent_name']} | {item['run_count']} | {item['success_rate']:.0%} | {confidence_text} | "
            f"{item['avg_latency_ms']}ms | {item['avg_tokens_per_run']} | ${item['total_cost_usd']:.2f} | "
            f"{item['retry_count']} | {item['escalation_count']} |"
        )
    return "\n".join(
        [
            f"# Jarvis Stats Report — {stats_payload['run_date'][:10]}",
            "",
            f"**Analysis window**: {stats_payload['analysis_window_start'] or 'all time'} → {stats_payload['analysis_window_end']}",
            f"**Runs analyzed**: {stats_payload['total_runs_analyzed']}",
            f"**Total agent executions**: {stats_payload['total_agent_executions']}",
            "",
            "## Per-Agent Summary",
            "",
            "| Agent | Runs | Success Rate | Avg Confidence | Avg Latency | Avg Tokens | Cost (period) | Retries | Escalations |",
            "|-------|------|-------------|----------------|-------------|------------|---------------|---------|-------------|",
            *(rows or ["| (none) | 0 | 0% | N/A | 0ms | 0 | $0.00 | 0 | 0 |"]),
        ]
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
