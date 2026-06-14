# Contract: Run Log JSON Schema

**Feature**: 003-phase2-agent-ecosystem
**Contract ID**: run-log-schema
**Version**: 1.0
**Created**: 2026-06-14

---

## Overview

Every Jarvis run produces a single JSON file at `jarvis/logs/{YYYY-MM-DD}/{run_id}.json`. The file contains an array of `AgentLogEntry` objects — one per agent executed in that run — plus a top-level `run` metadata object.

This file is:
- Written incrementally during the run (one entry appended after each agent completes)
- Synced to SharePoint via the Power Automate webhook alongside Markdown vault files
- Read by the CI Agent during bi-weekly analysis
- Never modified after the run completes

---

## Schema

```json
{
  "run": {
    "run_id": "string (UUID4, required)",
    "trace_id": "string (UUID4, required)",
    "workflow_id": "string (required) — overnight_task | ci_analysis | vault_maintenance | pr_review",
    "trigger_source": "string (required) — github_actions_cron | inbox_push | workflow_dispatch",
    "started_at": "string (ISO 8601 UTC, required)",
    "completed_at": "string (ISO 8601 UTC, required)",
    "overall_status": "string (required) — completed | partial | needs_clarification | failed",
    "task_id": "string (optional)"
  },
  "agents": [
    {
      "timestamp": "string (ISO 8601 UTC, required)",
      "run_id": "string (required)",
      "trace_id": "string (required)",
      "agent_name": "string (required) — orchestrator | research | gcp_discovery | obsidian_writer | validation | ci_agent | vault_maintenance | pr_review",
      "agent_version": "string (required) — semver e.g. '1.0.0'",
      "status": "string (required) — success | partial | skipped | failed",
      "latency_ms": "integer (required)",
      "token_usage": {
        "input": "integer (required)",
        "output": "integer (required)",
        "total": "integer (required)",
        "estimated_cost_usd": "float (required)"
      },
      "prompt_id": "string (optional)",
      "prompt_version": "string (optional)",
      "input_summary": "string (optional, max 200 chars)",
      "output_summary": "string (optional, max 200 chars)",
      "confidence_score": "float 0.0–1.0 (optional)",
      "validation_pass": "boolean (optional)",
      "tool_calls": ["string (optional)"],
      "error_type": "string (optional) — api_timeout | api_rate_limit | validation_fail | pii_detected | config_missing | parse_error | tool_error | webhook_fail",
      "retry_count": "integer (optional, default 0)",
      "skip_reason": "string (optional)",
      "fallback_target": "string (optional) — retry | human_review | null",
      "escalation_flag": "boolean (optional, default false)",
      "human_review_required": "boolean (optional, default false)",
      "partial_run": "boolean (optional, default false)"
    }
  ]
}
```

---

## Canonical Examples

### Successful run (2 agents)

```json
{
  "run": {
    "run_id": "a3f2b1c0-0001-4d2e-8b3a-123456789abc",
    "trace_id": "a3f2b1c0-0001-4d2e-8b3a-123456789abc",
    "workflow_id": "overnight_task",
    "trigger_source": "github_actions_cron",
    "started_at": "2026-06-15T23:00:12Z",
    "completed_at": "2026-06-15T23:08:44Z",
    "overall_status": "completed",
    "task_id": "task_20260615_001"
  },
  "agents": [
    {
      "timestamp": "2026-06-15T23:03:41Z",
      "run_id": "a3f2b1c0-0001-4d2e-8b3a-123456789abc",
      "trace_id": "a3f2b1c0-0001-4d2e-8b3a-123456789abc",
      "agent_name": "research",
      "agent_version": "1.0.0",
      "status": "success",
      "latency_ms": 3241,
      "token_usage": {
        "input": 1840,
        "output": 412,
        "total": 2252,
        "estimated_cost_usd": 0.0024
      },
      "prompt_id": "research_v1.2",
      "prompt_version": "1.2",
      "input_summary": "Task: Summarize GCP cost anomalies Q1. 3 vault notes retrieved.",
      "output_summary": "412-token context summary. Cache hit: false.",
      "confidence_score": 0.92,
      "validation_pass": true,
      "tool_calls": ["vault_reader.search_notes"],
      "retry_count": 0,
      "escalation_flag": false,
      "human_review_required": false
    },
    {
      "timestamp": "2026-06-15T23:08:44Z",
      "run_id": "a3f2b1c0-0001-4d2e-8b3a-123456789abc",
      "trace_id": "a3f2b1c0-0001-4d2e-8b3a-123456789abc",
      "agent_name": "obsidian_writer",
      "agent_version": "1.0.0",
      "status": "success",
      "latency_ms": 5103,
      "token_usage": {
        "input": 2300,
        "output": 890,
        "total": 3190,
        "estimated_cost_usd": 0.0031
      },
      "prompt_id": "obsidian_writer_v1.0",
      "prompt_version": "1.0",
      "input_summary": "TaskResult with research output. Writing task record + digest.",
      "output_summary": "Wrote jarvis/tasks/task_20260615_001.md and jarvis/digests/2026-06-15.md.",
      "confidence_score": 0.94,
      "validation_pass": true,
      "retry_count": 0,
      "escalation_flag": false,
      "human_review_required": false
    }
  ]
}
```

### Partial run (agent skipped after retry)

```json
{
  "run": {
    "run_id": "b7e1a2d0-0002-4f3c-9c4b-234567890bcd",
    "trace_id": "b7e1a2d0-0002-4f3c-9c4b-234567890bcd",
    "workflow_id": "overnight_task",
    "trigger_source": "inbox_push",
    "started_at": "2026-06-16T23:01:05Z",
    "completed_at": "2026-06-16T23:14:22Z",
    "overall_status": "partial",
    "task_id": "task_20260616_001"
  },
  "agents": [
    {
      "timestamp": "2026-06-16T23:10:38Z",
      "run_id": "b7e1a2d0-0002-4f3c-9c4b-234567890bcd",
      "trace_id": "b7e1a2d0-0002-4f3c-9c4b-234567890bcd",
      "agent_name": "obsidian_writer",
      "agent_version": "1.0.0",
      "status": "skipped",
      "latency_ms": 9134,
      "token_usage": {
        "input": 2100,
        "output": 890,
        "total": 2990,
        "estimated_cost_usd": 0.0032
      },
      "prompt_id": "obsidian_writer_v1.0",
      "prompt_version": "1.0",
      "confidence_score": 0.54,
      "validation_pass": false,
      "error_type": "validation_fail",
      "retry_count": 1,
      "skip_reason": "validation_score_below_threshold_after_retry",
      "fallback_target": "human_review",
      "escalation_flag": true,
      "human_review_required": true,
      "partial_run": true
    }
  ]
}
```

---

## Writer Responsibilities

`orchestrator/utils/run_logger.py` is responsible for:
- Generating `run_id` and `trace_id` at the start of each invocation (UUID4)
- Creating the JSON file at `jarvis/logs/{date}/{run_id}.json` with the `run` object
- Appending one `AgentLogEntry` after each agent completes
- Finalizing the `run.completed_at` and `run.overall_status` at the end of the pipeline
- Including the JSON log file in the Power Automate webhook payload under `files[]`

---

## Reader Responsibilities

`orchestrator/agents/ci_agent.py` is responsible for:
- Iterating all JSON files in `jarvis/logs/` within the analysis window
- Parsing agent entries by `agent_name` for per-agent scoring
- Skipping malformed files and logging a warning (never crashing on bad log data)

---

## Constraints

- `input_summary` and `output_summary` must not contain PII
- `error_type` must use the controlled vocabulary exactly (no free-form error strings)
- JSON files are append-only during a run; never modified after `completed_at` is set
- File size is bounded: max ~8 agents × ~1KB per entry = ~8KB per run file
