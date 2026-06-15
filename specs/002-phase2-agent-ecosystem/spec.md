# Feature Specification: Jarvis Phase 2 — Agent Ecosystem Expansion

**Feature ID**: 003-phase2-agent-ecosystem
**Created**: 2026-06-14
**Status**: Draft

---

## Overview

### Problem Statement

The Jarvis MVP executes overnight tasks reliably but operates as a black box: there is no structured record of what each agent did, no mechanism to detect when output quality degrades, no way to systematically improve prompts or routing decisions over time, and no tooling to keep the Obsidian vault organized as it grows. The operator has no early warning when something goes wrong, and accumulated knowledge about what works is stored only as freeform Markdown lesson files rather than as queryable, actionable data.

### Proposed Solution

Expand Jarvis from a task executor into a self-monitoring, continuously improving agent ecosystem by adding:

1. **Structured observability** — every agent run produces a queryable JSON log, giving the system a data foundation it currently lacks
2. **Output quality gates** — a Validation Agent scores every agent output before it is committed, enabling automatic retry and graceful degradation instead of silent failure
3. **Governance-safe continuous improvement** — a CI Agent analyzes logs bi-weekly and surfaces improvement recommendations for human approval, never deploying changes autonomously
4. **Vault health maintenance** — a Vault Maintenance Agent keeps the Obsidian vault organized automatically, handling low-risk fixes and queuing high-risk changes for operator review
5. **On-demand PR analysis** — a PR Review Agent produces structured pull request reviews on request, written to the vault only
6. **Prompt lifecycle management** — a library system that versions, tags, and tracks the performance of every prompt used across all agents

---

## Actors

| Actor | Role |
|-------|------|
| Operator (You) | Reviews CI reports, approves/rejects improvement recommendations via inbox task, reviews escalated failures in morning digest |
| Orchestrator Agent | Routes tasks to subagents; now enforces recovery logic (retry, skip-degrade) based on Validation Agent scores |
| Validation Agent | Scores every subagent output for quality, relevance, completeness, and compliance; triggers retry or skip-degrade |
| CI Agent | Analyzes structured logs bi-weekly; produces scored improvement recommendations; never auto-applies changes |
| Vault Maintenance Agent | Enforces vault organization standards; auto-fixes low-risk issues; proposes high-risk changes for operator approval |
| PR Review Agent | Analyzes GitHub pull requests on demand; writes structured reviews to vault only; never posts to GitHub |
| Research Agent | Unchanged from Phase 1 |
| GCP Discovery Agent | Unchanged from Phase 1 |
| Obsidian Writer Agent | Unchanged from Phase 1; now also writes structured JSON logs and CI reports to vault |

---

## User Scenarios & Testing

### Primary Flow: Observable Agent Run with Quality Gates

1. Operator commits a task to the inbox file
2. System runs the agent pipeline as in Phase 1
3. After each subagent completes, Validation Agent scores the output
4. If score ≥ 0.90: output is accepted and the pipeline continues
5. If score is 0.60–0.89: agent retries once; if retry score ≥ 0.60, output is accepted as partial
6. If score < 0.60 after retry: agent is skipped, TaskResult marked `partial`, digest entry flagged `[HUMAN REVIEW REQUIRED]`
7. Every agent execution produces a structured JSON log entry synced to SharePoint
8. Operator reads the morning digest and sees a quality score summary for the run

**Acceptance**: Operator can determine from the digest and vault logs exactly which agents ran, what scores they received, whether any retries occurred, and which (if any) outputs were skipped — all without reading raw log files.

### Primary Flow: Bi-Weekly CI Report Review

1. CI Agent runs automatically on Sunday and Wednesday nights
2. CI Agent reads all structured JSON logs since the last CI run
3. CI Agent scores each agent across: success rate, output quality, token efficiency, latency, recovery rate, and human intervention rate
4. CI Agent produces a human-readable report in the vault with ranked improvement recommendations
5. Each recommendation includes: the specific change proposed, the evidence supporting it, the projected improvement score, and the risk level
6. Operator reads the report in SharePoint/Obsidian and decides which recommendations to approve
7. To approve a recommendation, operator writes an inbox task: `apply CI recommendation R-{id}`
8. On the next run, Jarvis applies the approved change, archives the old prompt or config value, and logs the change

**Acceptance**: Operator can approve or reject any CI recommendation using only the morning digest and an inbox task. No direct code edits required. All applied changes are reversible via git history.

### Secondary Flow: Vault Maintenance

1. Vault Maintenance Agent runs automatically each Saturday night
2. Agent scans the vault for: broken internal links, naming convention violations, missing frontmatter, orphaned empty files, duplicate knowledge notes, and stale records
3. Low-risk issues (links, naming, empty files) are auto-fixed and committed directly
4. High-risk issues (duplicates, merge candidates, stale records > 90 days old) are written to a proposal report in the vault
5. Operator reviews proposals and approves high-risk actions via inbox task

**Acceptance**: After the first Saturday run, at least one auto-fix commit appears. Proposal report is readable in SharePoint. No vault content is destroyed without operator approval.

### Secondary Flow: On-Demand PR Review

1. Operator writes an inbox task with `agents: pr_review` and a GitHub PR URL or PR number
2. Jarvis fetches the PR diff and description using read-only GitHub API access
3. Research Agent retrieves relevant vault context (prior decisions, architecture notes)
4. PR Review Agent produces a structured review: change summary, risk assessment, specific concerns, suggested questions for the PR author, and an approval recommendation
5. Review is written to the vault as a task record, flagged `[HUMAN REVIEW REQUIRED]`
6. Operator reads the review and acts on it manually

**Acceptance**: PR review is in the vault within one run cycle of the inbox task being committed. No comment is posted to GitHub automatically under any circumstances.

### Edge Case: Validation Agent Itself Fails

1. Validation Agent crashes or returns a malformed response
2. System treats the scored agent's output as passing (assumes 0.90 score)
3. Validation Agent failure is logged as a separate error entry in the JSON run log
4. Operator sees a warning in the morning digest that Validation Agent had an error on that run
5. CI Agent flags the Validation Agent's reliability in the next bi-weekly report

**Acceptance**: A Validation Agent crash never halts a task run. The pipeline continues and the failure is visible in the digest.

### Edge Case: CI Recommendation Causes a Regression

1. Operator approves a CI recommendation and Jarvis applies the change
2. On subsequent runs, Validation Agent scores for the affected agent drop below the pre-change baseline
3. CI Agent detects the regression in the next bi-weekly cycle
4. CI Agent produces a rollback recommendation with evidence (before/after score comparison)
5. Operator approves rollback via inbox task; Jarvis restores the previous prompt or config from git history

**Acceptance**: Any applied CI change can be rolled back to the prior state via a single inbox task approval, without manual file editing.

---

## Functional Requirements

### Structured Logging

- **FR-01**: Every agent execution produces a structured JSON log record containing at minimum: timestamp, run ID, trace ID, workflow ID, agent name, agent version, status, latency in milliseconds, and token usage
- **FR-02**: JSON log files are written to the vault under `jarvis/logs/{date}/{run_id}.json` and synced to SharePoint via the existing Power Automate webhook
- **FR-03**: Every run shares a single `run_id` and `trace_id` across all agent executions, enabling end-to-end traceability of a workflow
- **FR-04**: Log records include optional fields when applicable: prompt ID and version, confidence score, validation pass/fail, retry count, error type, escalation flag, and skip reason
- **FR-05**: The error type field uses a controlled vocabulary: `api_timeout`, `api_rate_limit`, `validation_fail`, `pii_detected`, `config_missing`, `parse_error`, `tool_error`, `webhook_fail`

### Validation Agent

- **FR-06**: The Validation Agent runs inline after every subagent completes, before its output is committed to the TaskResult
- **FR-07**: The Validation Agent scores output across four dimensions: relevance to the task, completeness, compliance (PII-free, format correct), and format adherence
- **FR-08**: Scores follow a three-tier decision model: ≥ 0.90 accept; 0.60–0.89 retry agent once; < 0.60 skip agent and escalate
- **FR-09**: A Validation Agent failure (crash or malformed response) must never halt the task pipeline; the scored agent's output is treated as passing in this case
- **FR-10**: Validation scores for all agents are included in the morning digest summary

### Output Recovery

- **FR-11**: When a transient error occurs (timeout, rate limit), the system retries the affected agent once after a 30-second backoff before invoking the Validation Agent
- **FR-12**: When an agent is skipped due to a low validation score, the TaskResult status is set to `partial` and the skipped agent is listed in the digest with `[HUMAN REVIEW REQUIRED]`
- **FR-13**: Recovery decisions (retry, skip, escalate) are logged in the JSON run log with the error class and recovery action taken

### CI Agent

- **FR-14**: The CI Agent runs on a bi-weekly schedule: Sunday and Wednesday nights
- **FR-15**: The CI Agent analyzes structured JSON logs from all runs since its last execution
- **FR-16**: The CI Agent scores agents and workflows across seven weighted dimensions: success rate (25%), output quality (20%), validation pass rate (15%), token efficiency (15%), latency (10%), recovery rate (10%), and human intervention rate (5%)
- **FR-17**: A recommendation is surfaced only when the projected CI score improvement is ≥ 15%; changes with 5–14% projected improvement are flagged as testing candidates only; changes with < 5% improvement are discarded
- **FR-18**: Each recommendation in the CI report includes: the specific change proposed, the evidence from logs, the projected score delta, the risk level, and the exact inbox task text to approve it
- **FR-19**: The CI Agent never modifies prompts, configuration files, or the prompt library index directly; all changes require operator approval via inbox task
- **FR-20**: The CI Agent produces both a human-readable Markdown report (`jarvis/ci/ci_report_{date}.md`) and a machine-readable JSON scores file (`jarvis/ci/ci_scores_{date}.json`) for use in the next CI cycle
- **FR-21**: When an approved CI recommendation is applied, the previous prompt or config value is archived with a version suffix before the new value is written

### Prompt Library

- **FR-22**: All prompts used by agents are registered in a central metadata index at `prompts/library.json`
- **FR-23**: Each prompt entry records: prompt ID, title, linked agent, use case, tags, approval status, current version, version history with archived file paths, and performance metrics (average confidence score, validation pass rate, average latency, average tokens, sample size, last evaluated date)
- **FR-24**: When a new prompt version is applied, the previous version is archived to `prompts/versions/` with its version number appended to the filename
- **FR-25**: Prompt approval status follows four states: `draft`, `approved`, `testing`, `deprecated`
- **FR-26**: The CI Agent updates performance metrics in `library.json` after each bi-weekly analysis cycle

### Vault Maintenance Agent

- **FR-27**: The Vault Maintenance Agent runs automatically each Saturday night
- **FR-28**: The agent auto-fixes without approval: broken internal wikilinks, filename convention violations (kebab-case standard), missing standard frontmatter fields, and orphaned empty files
- **FR-29**: Auto-fix changes are committed with the message `vault: maintenance auto-fix [jarvis-skip]`
- **FR-30**: The agent proposes without auto-applying: duplicate knowledge notes, stale task records older than 90 days with no references, notes classified to the wrong folder, and merge candidates
- **FR-31**: Proposals are written to `jarvis/vault/maintenance_{date}.md` and synced to SharePoint; each proposal includes a proposal ID and the exact inbox task text to approve it
- **FR-32**: Any file write error during auto-fix aborts all writes for that run; the agent falls back to producing a report-only output

### PR Review Agent

- **FR-33**: The PR Review Agent is triggered by an inbox task containing `agents: pr_review` and a GitHub PR URL or PR number
- **FR-34**: The agent fetches PR diff and description using read-only GitHub API access only; no write operations to GitHub are permitted under any circumstances
- **FR-35**: The PR review output includes: a plain-English summary of changes, a risk assessment (HIGH / MED / LOW), specific concerns (security, logic, performance), suggested questions for the PR author, and an approval recommendation
- **FR-36**: PR review output is written to `jarvis/tasks/{task_id}.md` and flagged `[HUMAN REVIEW REQUIRED]`

### pm_workflow Integration

- **FR-37**: Jarvis Phase 2 writes all vault outputs to a dedicated `Jarvis/` root path within the existing SharePoint document library used by pm_workflow (which writes to `PM/`)
- **FR-38**: No changes are made to pm_workflow PowerShell scripts; the two systems coexist independently in the same library

### Safety & Compliance (Inherited and Extended)

- **FR-39**: All Phase 1 safety constraints remain in force: no PII, no auto-send, read-only GCP, approved services only
- **FR-40**: The PR Review Agent's GitHub token must be scoped to read-only access (`repo:read`); the codebase must contain no `PATCH`, `POST`, `PUT`, or `DELETE` calls to the GitHub API
- **FR-41**: CI recommendations that propose changes to safety-related logic (PII guard, auto-send prohibition) are automatically classified as HIGH risk regardless of their projected score improvement

---

## Success Criteria

| Criterion | Measure |
|-----------|---------|
| Full run observability | Operator can determine from the vault alone which agents ran, what scores they received, and whether any failures occurred — for any run in the past 30 days |
| Quality gate effectiveness | Zero instances of an agent output failing silently; all suboptimal outputs are either retried, skipped, or escalated visibly in the digest |
| CI recommendation quality | At least one actionable improvement recommendation appears in each bi-weekly CI report after the first 4 weeks of data accumulation |
| Approval loop reliability | An operator-approved CI recommendation is applied correctly on the next Jarvis run, with the prior state preserved and recoverable |
| Vault maintenance coverage | After the first Saturday run, the vault has zero broken internal links and all files conform to naming conventions |
| PR review turnaround | A PR review inbox task committed before 11 PM produces a complete review in the vault by the following morning |
| Prompt library completeness | All agent prompts are registered in `library.json` with performance data populated after the first two CI cycles |
| Regression safety | Any applied CI change that causes validation scores to drop is detected by the next CI cycle and a rollback recommendation is produced |

---

## Assumptions

- Phase 1 (001-jarvis-mvp) is complete and stable; all existing agents, contracts, and the Power Automate webhook are functioning
- The existing Power Automate webhook payload can be extended to include JSON log files alongside Markdown vault files with no structural changes to the flow
- `ubuntu-latest` GitHub Actions runners have Python 3.12 pre-installed; `setup-python` with pip caching is sufficient for dependency management
- The SharePoint document library has sufficient storage for structured JSON log files at the projected volume (~40 records/week)
- A read-only GitHub token (`repo:read` scope) can be added to GitHub Actions secrets without organizational approval barriers
- The operator reviews vault content in SharePoint or Obsidian at least once per weekday morning
- pm_workflow PowerShell scripts write exclusively to paths under `PM/` in the SharePoint library; no naming collisions with the `Jarvis/` path exist

---

## Constraints & Dependencies

| Constraint | Impact |
|------------|--------|
| No new approved services | All Phase 2 functionality must use: `anthropic`, `google-cloud-bigquery`, `requests`, `pyyaml`. GitHub API calls use `requests` (already approved). |
| No auto-deploy of CI changes | CI Agent is a recommendation engine only; every production-impacting change requires an explicit inbox task approval from the operator |
| No GitHub writes | PR Review Agent has read-only GitHub API access; no PR comments, reviews, or labels may be posted automatically |
| Vault Maintenance high-risk requires approval | Any vault action that modifies or deletes existing note content requires operator approval via inbox task |
| Phase 1 contracts unchanged | JSON log schema is additive; existing Markdown outputs, Power Automate payload structure, and inbox format are not modified |
| GCP service account still pending | GCP Discovery Agent remains daytime-only; this constraint carries forward from Phase 1 |

---

## Out of Scope (Phase 2)

- Absorbing pm_workflow PowerShell script logic into a Jarvis agent (Phase 3+)
- Overnight GCP Discovery Agent runs (blocked by pending service account approval)
- Email Classification Agent for auto-ingesting inbound Outlook requests
- Any write operations to GitHub (PR comments, issue labels, status checks)
- Real-time monitoring or alerting (Slack, email, Teams notifications)
- Multi-operator support or role-based access control
- Automated A/B testing of prompt variants without operator involvement

---

## Key Entities

| Entity | Description |
|--------|-------------|
| Run Log | Structured JSON file capturing every agent execution within a single Jarvis run; keyed by `run_id` |
| Run ID | UUID generated at the start of each Jarvis invocation; shared across all agent executions in that run |
| Trace ID | UUID linking all log entries for a single workflow; enables end-to-end traceability across agents |
| Validation Result | Scored assessment of a single agent output: confidence score, pass/fail, quality dimension breakdown, retry recommendation |
| CI Report | Human-readable Markdown file produced bi-weekly; contains ranked improvement recommendations with evidence and approval instructions |
| CI Scores File | Machine-readable JSON produced alongside the CI report; stores scoring baselines for the next CI cycle |
| Prompt Library Index | `prompts/library.json` — central metadata registry for all agent prompts; includes version history and performance metrics |
| Prompt Version Archive | Historical copy of a prompt stored in `prompts/versions/` when a new version is applied |
| Maintenance Report | Vault Maintenance Agent output listing high-risk proposals that require operator approval before execution |
| PR Review | Structured task record produced by the PR Review Agent; always flagged `[HUMAN REVIEW REQUIRED]` |
