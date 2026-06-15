# Contract: Run Log JSON Schema

**Feature**: 002-phase2-agent-ecosystem
**Contract ID**: run-log-schema
**Version**: 1.1
**Revised**: 2026-06-15

---

## Overview

Every Jarvis run produces a single JSON file at `jarvis/logs/{YYYY-MM-DD}/{run_id}.json`. The file contains a top-level `run` metadata object and an `agents` array — one entry per agent executed in that run.

This file is:
- Written incrementally during the run (one entry appended after each agent completes)
- Finalized when `run.completed_at` and `run.overall_status` are set at pipeline end
- Synced to SharePoint via the Power Automate webhook alongside Markdown vault files
- Read by the stats reporter during bi-weekly aggregation
- Never modified after the run completes

**PII note**: `input_summary` and `output_summary` are dynamic content with no PII filtering requirement. These fields remain within the Tyson Microsoft 365 tenant (SharePoint) and are not sent to any external system.

---

## Schema

```json
{
  "run": {
    "run_id": "string (UUID4, required)",
    "trace_id": "string (UUID4, required)",
    "workflow_id": "string (required) — overnight_task | stats_report",
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
      "agent_name": "string (required) — orchestrator | research | gcp_discovery | obsidian_writer | validation",
      "agent_version": "string (required) — semver e.g. '1.0.0'",
      "status": "string (required) — success | partial | skipped | failed",
      "latency_ms": "integer (required)",
      "token_usage": {
        "input": "integer (required)",
        "output": "integer (required)",
        "total": "integer (required)",
        "estimated_cost_usd": "float (required)"
      },
      "input_summary": "string (optional, max 200 chars — dynamic content, no PII filter)",
      "output_summary": "string (optional, max 200 chars — dynamic content, no PII filter)",
      "confidence_score": "float 0.0–1.0 (optional — present only for research and obsidian_writer)",
      "validation_pass": "boolean (optional)",
      "error_type": "string (optional) — api_timeout | api_rate_limit | validation_fail | config_missing | parse_error | tool_error | webhook_fail",
      "retry_count": "integer (optional, default 0)",
      "skip_reason": "string (optional)",
      "escalation_flag": "boolean (optional, default false)",
      "human_review_required": "boolean (optional, default false)",
      "partial_run": "boolean (optional, default false)"
    }
  ]
}
```

---

## Canonical Examples

### Successful run

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
    "task_id": "task-12345678-summarize-gcp-costs"
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
      "input_summary": "Task: Summarize GCP cost anomalies Q1. 3 vault notes retrieved.",
      "output_summary": "412-token context summary. Cache hit: false.",
      "confidence_score": 0.92,
      "validation_pass": true,
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
      "input_summary": "TaskResult with research context. Writing task record and digest.",
      "output_summary": "Wrote task record and daily digest.",
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
    "task_id": "task-12345679-draft-stakeholder-update"
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
      "input_summary": "TaskResult for stakeholder update draft.",
      "output_summary": "Output incomplete after retry — skipped.",
      "confidence_score": 0.54,
      "validation_pass": false,
      "error_type": "validation_fail",
      "retry_count": 1,
      "skip_reason": "validation_score_below_retry_accept_threshold",
      "escalation_flag": true,
      "human_review_required": true,
      "partial_run": true
    }
  ]
}
```

---

## Writer Responsibilities

`orchestrator/utils/run_logger.py` owns:
- Generating `run_id` and `trace_id` (UUID4) at the start of each invocation
- Creating the JSON file with the `run` object
- Appending one `AgentLogEntry` after each agent completes
- Finalizing `run.completed_at` and `run.overall_status` at pipeline end
- Including the JSON log in the Power Automate webhook payload

---

## Reader Responsibilities

`orchestrator/agents/stats_reporter.py` owns:
- Iterating all JSON files in `jarvis/logs/` within the analysis window
- Parsing agent entries by `agent_name` for per-agent aggregation
- Skipping malformed files with a warning (never crashing on bad log data)

---

## Constraints

- `agent_name` must use the controlled vocabulary exactly
- `error_type` must use the controlled vocabulary exactly (no free-form error strings)
- JSON files are append-only during a run; never modified after `completed_at` is set
- `estimated_cost_usd` must be non-zero for any agent that makes an Anthropic API call
- `confidence_score` is populated only for `research` and `obsidian_writer`; absent for all others
