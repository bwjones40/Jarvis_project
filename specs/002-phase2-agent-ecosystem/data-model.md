# Data Model: Jarvis Phase 2 — Agent Ecosystem Foundation

**Feature**: 002-phase2-agent-ecosystem
**Revised**: 2026-06-15

---

## Entity Overview

```
RunLog ──────────────────── AgentLogEntry (1:many)
                                 └── TokenUsage (1:1)

ValidationResult (1:1 per scored agent, inline in pipeline)
    └── QualityDimensions (1:1)

StatsReport ─────────────── AgentStats (1:many)
```

All entities from the original Phase 2 draft that belong to the CI recommendation engine, Vault Maintenance, Prompt Library, or PR Review have been removed. Those are Phase 3 entities.

---

## Entities

### RunLog

Top-level record for a single Jarvis invocation. One RunLog per GitHub Actions job execution.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| run_id | string (UUID4) | yes | Unique identifier for this invocation; shared across all AgentLogEntry records |
| trace_id | string (UUID4) | yes | Workflow-level trace identifier; same as run_id for single-workflow runs |
| workflow_id | string | yes | `overnight_task` or `stats_report` |
| trigger_source | string | yes | `github_actions_cron`, `inbox_push`, or `workflow_dispatch` |
| started_at | string (ISO 8601 UTC) | yes | When the run started |
| completed_at | string (ISO 8601 UTC) | yes | When the run completed |
| overall_status | string | yes | `completed`, `partial`, `needs_clarification`, `failed` |
| task_id | string | no | The inbox task ID being processed, if applicable |
| agent_entries | AgentLogEntry[] | yes | Ordered list of agent execution records |

**File location**: `jarvis/logs/{YYYY-MM-DD}/{run_id}.json`

**State transitions**: `in_progress` → `completed` | `partial` | `needs_clarification` | `failed`

---

### AgentLogEntry

One record per agent execution within a run.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| timestamp | string (ISO 8601 UTC) | yes | When this agent execution completed |
| run_id | string | yes | Foreign key to RunLog |
| trace_id | string | yes | Foreign key to RunLog trace |
| agent_name | string | yes | `orchestrator`, `research`, `gcp_discovery`, `obsidian_writer`, `validation` |
| agent_version | string | yes | Semver string e.g. `"1.0.0"`; hardcoded per agent file |
| status | string | yes | `success`, `partial`, `skipped`, `failed` |
| latency_ms | integer | yes | Wall-clock duration in milliseconds |
| token_usage | TokenUsage | yes | Token counts and estimated cost |
| input_summary | string | no | Plain-English description of what this agent received (dynamic; no PII filter required — stays within Tyson tenant) |
| output_summary | string | no | Plain-English description of what this agent produced (dynamic; no PII filter required — stays within Tyson tenant) |
| error_type | string | no | Controlled vocabulary: `api_timeout`, `api_rate_limit`, `validation_fail`, `config_missing`, `parse_error`, `tool_error`, `webhook_fail` |
| retry_count | integer | no | Number of retries attempted (0 if first attempt succeeded) |
| confidence_score | float | no | Validation Agent composite score (0.0–1.0); absent if Validation Agent not run |
| validation_pass | boolean | no | Whether the confidence score met the acceptance threshold |
| skip_reason | string | no | Why the agent was skipped, if status=`skipped` |
| escalation_flag | boolean | no | True if this entry requires human attention in the digest |
| human_review_required | boolean | no | True if this output was flagged `[HUMAN REVIEW REQUIRED]` |
| partial_run | boolean | no | True if this agent's skip caused TaskResult.status=`partial` |

---

### TokenUsage

Embedded in AgentLogEntry.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| input | integer | yes | Input token count |
| output | integer | yes | Output token count |
| total | integer | yes | input + output |
| estimated_cost_usd | float | yes | Estimated USD cost at current model pricing; non-zero after Phase 0 LLM wiring |

---

### ValidationResult

Produced inline by the Validation Agent for `research` and `obsidian_writer`. Not persisted to disk — key fields are written to `AgentLogEntry`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| agent_name | string | yes | The agent whose output was scored |
| run_id | string | yes | Foreign key to RunLog |
| confidence_score | float | yes | Composite score (0.0–1.0) |
| pass | boolean | yes | True if score meets acceptance threshold |
| retry_recommended | boolean | yes | True if score is in the retry window |
| escalate | boolean | yes | True if score requires skip and human review |
| quality_dimensions | QualityDimensions | yes | Per-dimension breakdown |
| notes | string | no | Free-text observation from the Validation Agent (max 300 chars) |

---

### QualityDimensions

Embedded in ValidationResult.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| relevance | float | yes | Output addresses the actual task request (0.0–1.0) |
| completeness | float | yes | All aspects of the task are covered (0.0–1.0) |
| actionability | float | yes | Output gives the operator something concrete to act on (0.0–1.0) |
| format_adherence | float | yes | Output matches the expected structure (0.0–1.0) |

**Composite formula**: `confidence_score = (relevance × 0.35) + (completeness × 0.30) + (actionability × 0.25) + (format_adherence × 0.10)`

---

### StatsReport

One record per stats report job execution. Written as both Markdown and JSON.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| stats_run_id | string | yes | Unique identifier for this stats run |
| run_date | string (ISO 8601 UTC) | yes | When this stats job executed |
| analysis_window_start | string (ISO 8601 UTC) | yes | Earliest log entry included; null on first run (all logs) |
| analysis_window_end | string (ISO 8601 UTC) | yes | Latest log entry included |
| total_runs_analyzed | integer | yes | Number of RunLog files examined |
| total_agent_executions | integer | yes | Total AgentLogEntry records examined |
| agent_stats | AgentStats[] | yes | Per-agent aggregated metrics |
| report_path | string | yes | Vault path to the Markdown report |
| scores_path | string | yes | Vault path to the JSON scores file |

**File locations**:
- `jarvis/ci/stats_{YYYY-MM-DD}.md` (human-readable)
- `jarvis/ci/stats_{YYYY-MM-DD}.json` (machine-readable)

---

### AgentStats

Embedded in StatsReport. One record per agent appearing in the analysis window.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| agent_name | string | yes | The agent being reported on |
| run_count | integer | yes | Number of executions in the analysis window |
| success_rate | float | yes | Proportion of executions with status=`success` |
| avg_confidence_score | float | no | Mean confidence score; present only for `research` and `obsidian_writer` |
| avg_latency_ms | integer | yes | Mean latency across executions |
| avg_tokens_per_run | integer | yes | Mean total tokens per execution |
| total_cost_usd | float | yes | Sum of estimated_cost_usd across all executions in window |
| retry_count | integer | yes | Total number of retries that fired in the window |
| escalation_count | integer | yes | Total number of executions with escalation_flag=true |

---

## State Transitions

### AgentLogEntry.status
```
pending → in_progress → success
                     → partial    (validation score in retry window, accepted after retry)
                     → skipped    (validation score below threshold after retry, or immediate skip)
                     → failed     (unrecoverable error; Validation Agent crash uses this for its own entry)
```

### RunLog.overall_status
```
in_progress → completed          (all agents succeeded)
            → partial            (one or more agents skipped due to validation)
            → needs_clarification (orchestrator returned clarification request)
            → failed             (unrecoverable pipeline failure)
```
