# Contract: Stats Report Schema

**Feature**: 002-phase2-agent-ecosystem
**Contract ID**: stats-report-schema
**Version**: 1.0
**Created**: 2026-06-15

---

## Overview

The stats report job produces two files per run: a human-readable Markdown report and a machine-readable JSON scores file. Both are written to `jarvis/ci/` and synced to SharePoint.

The stats reporter requires no Anthropic API call — it is pure log aggregation using the Python standard library.

**File locations**:
- `jarvis/ci/stats_{YYYY-MM-DD}.md` — human-readable
- `jarvis/ci/stats_{YYYY-MM-DD}.json` — machine-readable; `analysis_window_end` is consumed by the next stats run to determine the analysis window start

---

## JSON Schema

```json
{
  "stats_run_id": "string (UUID4, required)",
  "run_date": "string (ISO 8601 UTC, required)",
  "analysis_window_start": "string (ISO 8601 UTC, required) — null on first run",
  "analysis_window_end": "string (ISO 8601 UTC, required)",
  "total_runs_analyzed": "integer (required)",
  "total_agent_executions": "integer (required)",
  "agent_stats": [
    {
      "agent_name": "string (required) — orchestrator | research | gcp_discovery | obsidian_writer | validation",
      "run_count": "integer (required)",
      "success_rate": "float 0.0–1.0 (required)",
      "avg_confidence_score": "float 0.0–1.0 (optional) — present only for research and obsidian_writer",
      "avg_latency_ms": "integer (required)",
      "avg_tokens_per_run": "integer (required)",
      "total_cost_usd": "float (required)",
      "retry_count": "integer (required)",
      "escalation_count": "integer (required)"
    }
  ]
}
```

---

## Canonical Example

```json
{
  "stats_run_id": "e5f6a7b8-0005-4c3d-a1b2-567890123efg",
  "run_date": "2026-06-22T23:01:14Z",
  "analysis_window_start": "2026-06-15T23:00:00Z",
  "analysis_window_end": "2026-06-22T22:59:59Z",
  "total_runs_analyzed": 5,
  "total_agent_executions": 24,
  "agent_stats": [
    {
      "agent_name": "research",
      "run_count": 5,
      "success_rate": 1.0,
      "avg_confidence_score": 0.91,
      "avg_latency_ms": 3180,
      "avg_tokens_per_run": 2100,
      "total_cost_usd": 0.0112,
      "retry_count": 0,
      "escalation_count": 0
    },
    {
      "agent_name": "obsidian_writer",
      "run_count": 5,
      "success_rate": 0.8,
      "avg_confidence_score": 0.87,
      "avg_latency_ms": 5240,
      "avg_tokens_per_run": 3050,
      "total_cost_usd": 0.0201,
      "retry_count": 1,
      "escalation_count": 1
    },
    {
      "agent_name": "gcp_discovery",
      "run_count": 2,
      "success_rate": 1.0,
      "avg_latency_ms": 1820,
      "avg_tokens_per_run": 0,
      "total_cost_usd": 0.0,
      "retry_count": 0,
      "escalation_count": 0
    }
  ]
}
```

---

## Markdown Report Format

The `stats_{date}.md` file uses this structure:

```markdown
# Jarvis Stats Report — {date}

**Analysis window**: {start} → {end}
**Runs analyzed**: {total_runs_analyzed}
**Total agent executions**: {total_agent_executions}

## Per-Agent Summary

| Agent | Runs | Success Rate | Avg Confidence | Avg Latency | Avg Tokens | Cost (period) | Retries | Escalations |
|-------|------|-------------|----------------|-------------|------------|---------------|---------|-------------|
| research | 5 | 100% | 0.91 | 3180ms | 2100 | $0.01 | 0 | 0 |
| obsidian_writer | 5 | 80% | 0.87 | 5240ms | 3050 | $0.02 | 1 | 1 |
| gcp_discovery | 2 | 100% | N/A | 1820ms | 0 | $0.00 | 0 | 0 |
```

---

## Analysis Window Logic

On **first run** (no prior `jarvis/ci/stats_*.json` exists):
- `analysis_window_start`: null (scan all available logs)
- Scan all files under `jarvis/logs/`

On **subsequent runs**:
- Find the most recent file matching `jarvis/ci/stats_*.json`
- Read `analysis_window_end` from that file
- Set current run's `analysis_window_start` to that timestamp
- Scan only logs with `run.started_at` after `analysis_window_start`

---

## Constraints

- `avg_confidence_score` is only present for `research` and `obsidian_writer`; absent for all other agents
- `total_cost_usd` for `gcp_discovery` is always 0.0 (no Anthropic API calls)
- Malformed or unparseable log files are skipped with a warning; they do not fail the stats run
- `analysis_window_end` must be written accurately — downstream stats runs depend on it for their window calculation
