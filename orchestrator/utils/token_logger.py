"""Token usage helpers for agent execution records."""

from __future__ import annotations

from typing import Any


PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.0},
}


def log_agent_run(
    agent_name: str,
    model: str,
    usage: Any,
    duration: float,
    output: Any,
    errors: list[str],
) -> dict[str, Any]:
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    return {
        "agent_name": agent_name,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_seconds": float(duration),
        "output": output,
        "errors": errors,
    }


def calculate_cost(agent_runs: list[dict[str, Any]]) -> float:
    total_cost = 0.0
    for run in agent_runs:
        pricing = PRICING.get(run["model"])
        if not pricing:
            continue
        total_cost += (run["input_tokens"] / 1_000_000.0) * pricing["input"]
        total_cost += (run["output_tokens"] / 1_000_000.0) * pricing["output"]
    return round(total_cost, 4)
