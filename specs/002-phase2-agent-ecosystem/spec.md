# Feature Specification: Jarvis Phase 2 — Agent Ecosystem Foundation

**Feature ID**: 002-phase2-agent-ecosystem
**Created**: 2026-06-14
**Revised**: 2026-06-15
**Status**: Active

---

## Overview

### Problem Statement

The Jarvis MVP executes overnight tasks as a deterministic pipeline: it never calls the Anthropic API at runtime, produces no queryable record of what each agent did, and gives the operator no visibility when output quality is poor. There is no way to detect silent failures, no structured data to improve the system over time, and no morning signal when something went wrong. The system also has several stability gaps — task ID collisions, no CI regression gate, overlapping runs, and a Power Automate flow that always creates rather than updates vault notes.

### Proposed Solution

Transform Jarvis from a deterministic template pipeline into a real LLM-backed system with structured observability and output quality gates, in three sequential sprints preceded by a mandatory stabilization phase:

1. **Phase 0 — Stabilization**: Fix known gaps before any new feature lands — wire real Anthropic API calls, add CI regression testing, fix task IDs, prevent run collisions, update the Power Automate flow to upsert vault notes, and resolve the Node.js 24 deprecation warning.
2. **Sprint 1 — Structured Logging**: Every agent run produces a queryable JSON log file synced to SharePoint, giving the system a data foundation it currently lacks.
3. **Sprint 2 — Validation Agent**: Every research and obsidian_writer output is scored for quality before being committed, enabling retry and graceful degradation instead of silent failure.
4. **Sprint 3 — Monitoring**: The morning digest surfaces per-run quality scores, and a bi-weekly stats report provides trend visibility across runs.

---

## Actors

| Actor | Role |
|-------|------|
| Operator | Reads morning digest and weekly stats report; acts on escalated failures; approves no automated changes in this phase |
| Orchestrator Agent | Routes tasks to subagents; enforces retry/skip logic based on Validation Agent scores |
| Research Agent | Vault keyword search and context retrieval; now backed by real Claude API call; output scored by Validation Agent |
| GCP Discovery Agent | Unchanged from Phase 1; daytime-only; validated structurally (exit code + JSON parse), not by Validation Agent |
| Obsidian Writer Agent | Synthesizes task results into digest and task records; now backed by real Claude API call; output scored by Validation Agent |
| Validation Agent | New in Sprint 2; scores research and obsidian_writer outputs across four quality dimensions; drives retry/skip decisions |
| Stats Reporter | New in Sprint 3; pure log aggregation job (no LLM); produces bi-weekly stats report from JSON run logs |

---

## User Scenarios & Testing

### Primary Flow: LLM-Backed Overnight Run with Observability (Post-Phase 0 + Sprint 1)

1. Operator commits a task to `jarvis/inbox.md`
2. GitHub Actions triggers the `run-jarvis` job (queued if another run is in progress)
3. Orchestrator calls the Anthropic API with the real orchestrator prompt
4. Research Agent calls the Anthropic API with the real research prompt; vault context returned
5. Obsidian Writer calls the Anthropic API with the real obsidian_writer prompt; digest and task record produced
6. Each agent execution writes a structured JSON log entry to `jarvis/logs/{date}/{run_id}.json`
7. JSON log is included in the Power Automate webhook payload and synced to SharePoint
8. Operator reads the morning digest in SharePoint/Obsidian

**Acceptance**: JSON log exists in SharePoint after every overnight run. Log contains real token usage counts (not zero). Task IDs are unique across runs. No overlapping runs produce conflicting logs.

---

### Primary Flow: Observable Run with Quality Gates (Post-Sprint 2)

1. Operator commits a task to `jarvis/inbox.md`
2. Pipeline runs as above
3. After research completes, Validation Agent scores the output (relevance, completeness, actionability, format)
4. If score ≥ 0.90: output accepted, pipeline continues
5. If score 0.60–0.89: research retries once; if retry score ≥ 0.80, accepted; otherwise skipped and flagged
6. If score < 0.60: research skipped immediately, task record flagged `[HUMAN REVIEW REQUIRED]`
7. Same scoring applied to obsidian_writer output
8. All validation scores written to the JSON run log
9. Morning digest includes a "Run Quality Summary" table showing each agent's score and status

**Acceptance**: Operator can determine from the digest alone which agents ran, what scores they received, whether any retries occurred, and which (if any) outputs were skipped — without reading raw log files.

---

### Primary Flow: Bi-Weekly Stats Report (Post-Sprint 3)

1. Stats report job runs automatically on Sunday and Tuesday at 11PM UTC
2. Job reads all JSON run logs since the most recent stats report
3. Aggregates per-agent metrics: run count, success rate, average confidence score, average latency, average tokens and cost, retry count, escalation count
4. Produces `jarvis/ci/stats_{date}.md` (human-readable) and `jarvis/ci/stats_{date}.json` (machine-readable)
5. Both files synced to SharePoint via existing webhook
6. Operator reads the stats report in SharePoint on Monday or Wednesday morning

**Acceptance**: Stats report appears in SharePoint within 5 minutes of the Sunday/Tuesday 11PM job completing. Report contains data for all agents. On first run, all available logs are included.

---

### Edge Case: Validation Agent Crash

1. Validation Agent crashes or returns a malformed response
2. System treats the scored agent's output as passing (synthetic confidence score: 0.90)
3. Validation Agent failure logged as a separate error entry in the run JSON log with `status: failed`
4. Operator sees a warning in the morning digest that the Validation Agent had an error on that run
5. Pipeline continues — the crash never halts a task run

**Acceptance**: A Validation Agent crash never halts the overnight pipeline. The failure is visible in the digest and log.

---

### Edge Case: First Stats Report Run

1. No prior stats report exists in `jarvis/ci/`
2. Stats reporter scans all available JSON logs regardless of date
3. Produces report covering the full available history
4. Subsequent runs use the `analysis_window_end` timestamp from the most recent stats JSON to determine the start of the next window

**Acceptance**: First stats report runs successfully with no prior baseline. No errors due to missing previous report.

---

## Functional Requirements

### Phase 0 — Stabilization

- **FR-P0-01**: Wire real Anthropic API calls into `research.py` using `claude-haiku-4-5`; load prompt from `prompts/research.md` at runtime; implement single retry on API error; feed token counts to existing `token_logger`
- **FR-P0-02**: Wire real Anthropic API calls into `obsidian_writer.py` using `claude-sonnet-4-6`; load prompt from `prompts/obsidian_writer.md` at runtime; implement single retry on API error; feed token counts to existing `token_logger`
- **FR-P0-03**: Add `python -m unittest discover -s tests` as a CI step in `jarvis.yml`, running before the main Jarvis job; any test failure must block the run
- **FR-P0-04**: Unit tests must be updated within each sprint to cover new functionality introduced in that sprint; tests covering only Phase 1 behavior are not sufficient regression coverage for Phase 2 changes
- **FR-P0-05**: Task IDs use `GITHUB_RUN_ID` when running in GitHub Actions (`GITHUB_ACTIONS=true`); fall back to a UTC timestamp (`YYYYMMDD-HHMMSS`) for local `--dry-run` executions
- **FR-P0-06**: Add workflow concurrency control to `jarvis.yml`: `group: jarvis-run`, `cancel-in-progress: false`; a second triggered run queues rather than cancelling the in-progress run
- **FR-P0-07**: Change committed default `pii.mode` in `config/settings.yaml` from `off` to `standard`; PII enforcement applies only to content sent to the Anthropic API (external tenant boundary); SharePoint-bound outputs (JSON logs, Markdown vault files) have no PII enforcement requirement
- **FR-P0-08**: Update `actions/checkout` and `actions/setup-python` in `jarvis.yml` to versions that natively target Node.js 24; remove the `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` workaround env var
- **FR-P0-09**: Update `Jarvis_Create_File_Flow` in Power Automate to check whether the target file path already exists in the Obsidian vault before writing; if the file exists, replace its content entirely (full overwrite); if net new, create the file; no append behavior

---

### Sprint 1 — Structured Logging

- **FR-01**: Every agent execution produces a structured JSON log record written to `jarvis/logs/{YYYY-MM-DD}/{run_id}.json`
- **FR-02**: Each run shares a single UUID4 `run_id` and `trace_id` generated at the start of the main execution block in `orchestrator/main.py`; both values are passed to all agent calls and log entries for that run
- **FR-03**: The `RunLog` JSON file contains a `run` object and an `agents` array; the `run` object is written at start and finalized at completion with `completed_at` and `overall_status`
- **FR-04**: Each `AgentLogEntry` in the `agents` array contains at minimum: `timestamp`, `run_id`, `trace_id`, `agent_name`, `agent_version`, `status`, `latency_ms`, `token_usage` (input, output, total, estimated_cost_usd), `input_summary`, `output_summary`
- **FR-05**: `input_summary` and `output_summary` are dynamic plain-English descriptions of what each agent received and produced; no PII filtering is required as these fields remain within the Tyson Microsoft 365 tenant (SharePoint)
- **FR-06**: Optional fields on `AgentLogEntry` include: `error_type` (controlled vocabulary: `api_timeout`, `api_rate_limit`, `validation_fail`, `config_missing`, `parse_error`, `tool_error`, `webhook_fail`), `retry_count`, `escalation_flag`, `human_review_required`; Sprint 2 adds: `confidence_score`, `validation_pass`, `skip_reason`
- **FR-07**: `trigger_source` field on the `RunLog` is set to: `github_actions_cron` (scheduled run), `inbox_push` (push to inbox.md), or `workflow_dispatch` (manual trigger)
- **FR-08**: The JSON log file is included in the Power Automate webhook payload alongside existing Markdown vault files and synced to SharePoint under `Jarvis/logs/{date}/{run_id}.json`
- **FR-09**: Every agent file includes an `agent_version = "1.0.0"` constant; this value is written to `AgentLogEntry.agent_version` on every run
- **FR-10**: `token_usage.estimated_cost_usd` is populated using current model pricing from the existing `token_logger`; values must be non-zero after Phase 0 LLM wiring is complete

---

### Sprint 2 — Validation Agent

- **FR-11**: The Validation Agent runs inline after `research` and `obsidian_writer` complete, before their outputs are committed to `TaskResult`; it does NOT run after `gcp_discovery` or `orchestrator`
- **FR-12**: `gcp_discovery` output is validated structurally only: confirm command exit code is 0 and output is parseable JSON; no Validation Agent call is made
- **FR-13**: The Validation Agent uses `claude-haiku-4-5` and the prompt at `prompts/validation.md`
- **FR-14**: The Validation Agent scores output across four dimensions using a composite formula: `confidence_score = (relevance × 0.35) + (completeness × 0.30) + (actionability × 0.25) + (format_adherence × 0.10)`
  - `relevance`: output addresses the actual task request (0.0–1.0)
  - `completeness`: all aspects of the task are covered (0.0–1.0)
  - `actionability`: output gives the operator something concrete to act on (0.0–1.0)
  - `format_adherence`: output matches the expected structure (0.0–1.0)
- **FR-15**: Three-tier decision model (all thresholds configurable in `config/settings.yaml` under `validation:`):
  - `confidence_score ≥ 0.90` (`pass_threshold`): accept output, continue pipeline
  - `0.60 ≤ confidence_score < 0.90` (`retry_min_threshold`): retry agent once; if retry score ≥ 0.80 (`retry_accept_threshold`), accept; otherwise skip agent and set `escalation_flag: true`
  - `confidence_score < 0.60`: skip agent immediately, set `escalation_flag: true`, flag `[HUMAN REVIEW REQUIRED]`
- **FR-16**: When any agent is skipped due to validation failure, set `TaskResult.status = "partial"` and add the skipped agent name and reason to the digest with `[HUMAN REVIEW REQUIRED]` prefix
- **FR-17**: A Validation Agent crash (exception or malformed response) must never halt the pipeline; return a synthetic `ValidationResult` with `confidence_score: 0.90`, `notes: "SYNTHETIC: Validation Agent error"`, log the crash as a separate `AgentLogEntry` with `agent_name: "validation"` and `status: "failed"`
- **FR-18**: Setting the environment variable `JARVIS_VALIDATION_OVERRIDE_SCORE` to a float value (e.g., `0.45`) causes the Validation Agent to return that score for all agents in that run; used for testing retry/skip logic without mocking internals
- **FR-19**: Validation scores for all agents are written to the JSON run log under the relevant `AgentLogEntry` fields: `confidence_score`, `validation_pass`, `retry_count`, `skip_reason`

---

### Sprint 3 — Monitoring

- **FR-20**: The morning digest produced by `obsidian_writer.py` includes a new "Run Quality Summary" section after the task summary: a Markdown table with one row per agent showing agent name, confidence score (or "N/A" if not validated), pass/fail status, retry count, and escalation flag
- **FR-21**: The stats report job is a separate GitHub Actions job named `run-stats-report` with cron schedule `0 23 * * 0,2` (Sunday and Tuesday at 11PM UTC)
- **FR-22**: The stats report job runs `python orchestrator/main.py --mode stats_report`; the `--mode` flag handler routes to the stats reporter without executing the task pipeline
- **FR-23**: The stats reporter reads all JSON log files in `jarvis/logs/` within the analysis window; on the first run (no prior stats report exists), it analyzes all available logs; on subsequent runs, it reads `analysis_window_end` from the most recent `jarvis/ci/stats_*.json` to determine the window start
- **FR-24**: The stats report includes per-agent rows for all agents that appear in the log window: `orchestrator`, `research`, `gcp_discovery`, `obsidian_writer`, `validation`; each row contains: run count, success rate, average confidence score (validated agents only; "N/A" for others), average latency (ms), average tokens per run, estimated cost for the period, retry count, escalation count
- **FR-25**: The stats reporter writes two output files: `jarvis/ci/stats_{YYYY-MM-DD}.md` (human-readable Markdown) and `jarvis/ci/stats_{YYYY-MM-DD}.json` (machine-readable, includes `analysis_window_start` and `analysis_window_end` timestamps)
- **FR-26**: Both stats output files are included in the Power Automate webhook payload and synced to SharePoint; the stats job uses the same `post_files()` utility as the main run
- **FR-27**: The stats reporter requires no Anthropic API call; it is pure log aggregation using the Python standard library and `pyyaml`

---

## Success Criteria

| Criterion | Measure |
|-----------|---------|
| Real LLM execution | Token counts in every agent log entry are non-zero after Phase 0 completes |
| Regression safety | All 50+ existing unit tests pass in CI on every push; new tests cover each sprint's functionality |
| Run uniqueness | No two vault task records share the same task ID across any sequence of runs |
| Log availability | JSON log file exists in SharePoint within 5 minutes of every overnight run completing |
| Full run observability | Operator can determine from the vault alone which agents ran, token costs, and any failures — for any run in the past 30 days |
| Quality gate effectiveness | Zero silent agent failures after Sprint 2; all suboptimal outputs visible in the digest with `[HUMAN REVIEW REQUIRED]` flag |
| Digest quality visibility | Morning digest includes Run Quality Summary table on every run after Sprint 2 |
| Stats report availability | Stats report appears in SharePoint by Monday and Wednesday morning after the respective Sunday/Tuesday runs |
| Vault note integrity | Power Automate flow correctly updates existing vault notes without creating duplicate files |
| Zero regression | Existing Phase 1 agent behavior for valid inputs is unchanged by any Phase 2 modification |

---

## Assumptions

- Phase 1 (001-jarvis-mvp) is complete and stable; all existing agents, contracts, and the Power Automate webhook are functioning
- `prompts/research.md` and `prompts/obsidian_writer.md` contain valid system prompts ready for runtime use; no new prompt authoring is required in Phase 0 beyond confirming current prompt files work with the API
- The `ANTHROPIC_API_KEY` secret in GitHub Actions is valid for real API calls (the current workflow only smoke-tests connectivity; Phase 0 wiring will be the first real call)
- `ubuntu-latest` GitHub Actions runners have Python 3.12 pre-installed; no new dependencies are required
- The Power Automate flow has access to a "check file existence" action or equivalent logic to implement upsert behavior
- The operator reviews vault content in SharePoint or Obsidian at least once per weekday morning
- JSON log files at ~8–12KB per run will not exceed Power Automate payload limits
- The Tyson Microsoft 365 tenant boundary is the PII enforcement boundary; content within that boundary (SharePoint, Power Automate, OneDrive) requires no PII enforcement

---

## Constraints & Dependencies

| Constraint | Impact |
|------------|--------|
| No new approved dependencies | All Phase 2 functionality must use existing packages: `anthropic`, `google-cloud-bigquery`, `requests`, `pyyaml` |
| No auto-deploy of any changes | All agent outputs are vault-only; no automated writes to external systems |
| Phase 0 must complete before Sprint 1 | LLM wiring is a prerequisite for meaningful token counts in logs; regression gate is a prerequisite for safe pipeline modifications |
| GCP service account still pending | GCP Discovery Agent remains daytime-only; this constraint carries forward from Phase 1 |
| GitHub Actions runner has no SharePoint access | Vault Maintenance (scanning SharePoint vault files) is not possible in this phase; deferred to Phase 3 |
| Validation Agent validates only research and obsidian_writer | gcp_discovery uses structural validation only; orchestrator output is not scored |

---

## Out of Scope — Phase 2

The following were considered and explicitly deferred to Phase 3:

| Feature | Reason for Deferral |
|---------|---------------------|
| CI recommendation engine | Requires weeks of Validation Agent data to produce meaningful recommendations; premature to build before baseline data exists |
| PR Review Agent | Clean standalone feature; deprioritized in favor of foundational observability |
| Vault Maintenance — auto-fix (4A) | GitHub Actions runner cannot access SharePoint vault files; requires a SharePoint read path design not yet defined |
| Vault Maintenance — proposals (4B) | Depends on 4A and on Validation Agent being calibrated; both Phase 3 |
| Prompt Library (`library.json`, `prompts/versions/`) | Its main consumer is the CI recommendation engine; building it without a consumer adds maintenance burden with no value |

---

## Key Entities

| Entity | Description |
|--------|-------------|
| RunLog | JSON file capturing a single Jarvis invocation; contains one `run` object and an `agents` array; keyed by `run_id` |
| Run ID | UUID4 generated at the start of each invocation; shared across all AgentLogEntry records in the run |
| Trace ID | UUID4 linking all log entries for a single workflow; same as `run_id` for single-workflow runs |
| AgentLogEntry | One record per agent execution within a run; appended after each agent completes |
| TokenUsage | Embedded in AgentLogEntry; records input/output/total tokens and estimated USD cost |
| ValidationResult | Scored assessment of a single agent output; composite score drives accept/retry/skip decision |
| QualityDimensions | Per-dimension breakdown within ValidationResult: relevance, completeness, actionability, format_adherence |
| StatsReport | Bi-weekly aggregation of AgentLogEntry records; one row per agent per analysis window |
