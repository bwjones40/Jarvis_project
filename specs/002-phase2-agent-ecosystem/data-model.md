# Data Model: Jarvis Phase 2 — Agent Ecosystem Expansion

**Feature**: 003-phase2-agent-ecosystem
**Created**: 2026-06-14

---

## Entity Overview

```
RunLog ──────────────────── AgentLogEntry (1:many)
                                 │
                                 ├── ValidationResult (1:1 per scored agent)
                                 └── ErrorRecord (0:1)

CIRun ───────────────────── CIRecommendation (1:many)
   └── CIScoresSnapshot

PromptLibrary ───────────── PromptEntry (1:many)
                                 └── PromptVersion (1:many)

VaultMaintenanceRun ─────── MaintenanceAutoFix (1:many)
                         └── MaintenanceProposal (1:many)

PRReview (extends TaskResult from Phase 1)
```

---

## Entities

### RunLog

Top-level record for a single Jarvis invocation. One RunLog per GitHub Actions job execution.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| run_id | string (UUID4) | yes | Unique identifier for this invocation; shared across all AgentLogEntry records in the run |
| trace_id | string (UUID4) | yes | Workflow-level trace identifier; same as run_id for single-workflow runs |
| workflow_id | string | yes | Name of the workflow type: `overnight_task`, `ci_analysis`, `vault_maintenance`, `pr_review` |
| trigger_source | string | yes | What triggered the run: `github_actions_cron`, `inbox_push`, `workflow_dispatch` |
| started_at | string (ISO 8601 UTC) | yes | When the run started |
| completed_at | string (ISO 8601 UTC) | yes | When the run completed (including all agents) |
| overall_status | string | yes | `completed`, `partial`, `needs_clarification`, `failed` |
| task_id | string | no | The inbox task ID being processed, if applicable |
| agent_entries | AgentLogEntry[] | yes | Ordered list of agent execution records for this run |

**File location**: `jarvis/logs/{YYYY-MM-DD}/{run_id}.json`

**State transitions**: `in_progress` → `completed` | `partial` | `needs_clarification` | `failed`

---

### AgentLogEntry

One record per agent execution within a run. Appended to the run's JSON file after each agent completes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| timestamp | string (ISO 8601 UTC) | yes | When this agent execution completed |
| run_id | string | yes | Foreign key to RunLog |
| trace_id | string | yes | Foreign key to RunLog trace |
| agent_name | string | yes | One of: `orchestrator`, `research`, `gcp_discovery`, `obsidian_writer`, `validation`, `ci_agent`, `vault_maintenance`, `pr_review` |
| agent_version | string | yes | Semver string (e.g. `"1.0.0"`); hardcoded per agent file |
| status | string | yes | `success`, `partial`, `skipped`, `failed` |
| latency_ms | integer | yes | Wall-clock duration in milliseconds |
| token_usage | TokenUsage | yes | Input/output/total tokens and estimated cost |
| prompt_id | string | no | ID of the prompt used (from `library.json`) |
| prompt_version | string | no | Version of the prompt used |
| input_summary | string | no | Brief plain-English description of what this agent received |
| output_summary | string | no | Brief plain-English description of what this agent produced |
| confidence_score | float | no | Validation Agent score for this output (0.0–1.0); absent if Validation Agent was not run |
| validation_pass | boolean | no | Whether the confidence score met the acceptance threshold |
| tool_calls | string[] | no | List of utility functions called (e.g. `["vault_reader.search_notes"]`) |
| error_type | string | no | Controlled vocabulary: `api_timeout`, `api_rate_limit`, `validation_fail`, `pii_detected`, `config_missing`, `parse_error`, `tool_error`, `webhook_fail` |
| retry_count | integer | no | Number of retries attempted (0 if first attempt succeeded) |
| skip_reason | string | no | Why the agent was skipped, if status=`skipped` |
| fallback_target | string | no | What the system fell back to: `retry`, `human_review`, null |
| escalation_flag | boolean | no | True if this entry requires human attention in the digest |
| human_review_required | boolean | no | True if this output was flagged `[HUMAN REVIEW REQUIRED]` |
| partial_run | boolean | no | True if this agent's failure caused TaskResult.status=`partial` |

---

### TokenUsage

Embedded in AgentLogEntry.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| input | integer | yes | Input token count |
| output | integer | yes | Output token count |
| total | integer | yes | input + output |
| estimated_cost_usd | float | yes | Estimated USD cost at current model pricing |

---

### ValidationResult

Produced by the Validation Agent for each scored agent. Embedded in or linked from AgentLogEntry.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| agent_name | string | yes | The agent whose output was scored |
| run_id | string | yes | Foreign key to RunLog |
| confidence_score | float | yes | Composite score (0.0–1.0) |
| pass | boolean | yes | True if confidence_score ≥ 0.90 or retry score ≥ 0.60 |
| retry_recommended | boolean | yes | True if score is in the 0.60–0.89 retry window |
| escalate | boolean | yes | True if score < 0.60 after retry |
| quality_dimensions | QualityDimensions | yes | Per-dimension breakdown |
| notes | string | no | Free-text observation from the Validation Agent |
| calibration_sample_size | integer | no | Number of prior scored executions for this agent (used for self-calibration tracking) |

---

### QualityDimensions

Embedded in ValidationResult.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| relevance | float | yes | How relevant the output is to the task request (0.0–1.0) |
| completeness | float | yes | Whether the output addresses all aspects of the task (0.0–1.0) |
| compliance | float | yes | Whether the output is PII-free and format-compliant (0.0–1.0) |
| format_adherence | float | yes | Whether the output matches the expected structure (0.0–1.0) |

---

### CIRun

One record per CI Agent execution (bi-weekly).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| ci_run_id | string | yes | Unique identifier for this CI analysis cycle |
| run_date | string (ISO 8601 UTC) | yes | When this CI run executed |
| analysis_window_start | string (ISO 8601 UTC) | yes | Earliest log entry included in this analysis |
| analysis_window_end | string (ISO 8601 UTC) | yes | Latest log entry included in this analysis |
| total_runs_analyzed | integer | yes | Number of Jarvis runs examined |
| total_agent_executions | integer | yes | Total agent-level records examined |
| agent_scores | AgentScore[] | yes | Per-agent composite scores |
| recommendations | CIRecommendation[] | yes | Ranked list of improvement recommendations |
| report_path | string | yes | Vault path to the human-readable Markdown report |
| scores_path | string | yes | Vault path to the machine-readable JSON scores file |

**File location**: `jarvis/ci/ci_scores_{YYYY-MM-DD}.json`

---

### AgentScore

Embedded in CIRun. One record per agent analyzed.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| agent_name | string | yes | The agent being scored |
| composite_score | float | yes | Weighted composite CI score (0.0–1.0) |
| success_rate | float | yes | Proportion of executions with status=`success` |
| avg_output_quality | float | yes | Mean confidence score across all scored executions |
| validation_pass_rate | float | yes | Proportion of executions where validation_pass=true |
| token_efficiency | float | yes | Normalized score: useful output tokens / total tokens |
| avg_latency_ms | integer | yes | Mean latency across executions |
| recovery_rate | float | yes | Proportion of retry attempts that succeeded |
| human_intervention_rate | float | yes | Proportion of executions that set escalation_flag=true |
| sample_size | integer | yes | Number of executions analyzed |

---

### CIRecommendation

Embedded in CIRun. One record per proposed improvement.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| recommendation_id | string | yes | Sequential identifier (e.g. `R-001`); referenced in inbox approval tasks |
| type | string | yes | `prompt_improvement`, `routing_change`, `config_change`, `threshold_adjustment` |
| target_agent | string | yes | The agent this recommendation affects |
| current_value_ref | string | yes | Reference to the current prompt/config/threshold (e.g. `prompts/research.md v1.2`) |
| proposed_change_summary | string | yes | Plain-English description of what would change |
| evidence | string[] | yes | List of log-based evidence items supporting the recommendation |
| ci_score_delta | float | yes | Projected improvement in composite CI score |
| risk_level | string | yes | `LOW`, `MED`, `HIGH` |
| recommendation_status | string | yes | `pending`, `approved`, `rejected`, `applied`, `rolled_back` |
| approval_inbox_text | string | yes | Exact text the operator must put in the inbox to approve |
| expires_after_ci_run | string | no | This recommendation auto-expires if not approved by this CI run date |

---

### PromptEntry

One record per prompt registered in the library. Stored as an array in `prompts/library.json`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| prompt_id | string | yes | Unique identifier including version (e.g. `research_v1.2`) |
| title | string | yes | Human-readable name |
| file | string | yes | Repo-relative path to the current prompt file |
| linked_agent | string | yes | Name of the agent that uses this prompt |
| use_case | string | yes | What task this prompt performs |
| tags | string[] | yes | Categorization tags |
| status | string | yes | `draft`, `approved`, `testing`, `deprecated` |
| version | string | yes | Current version string (e.g. `"1.2"`) |
| version_history | PromptVersion[] | yes | Ordered list of prior versions |
| performance | PromptPerformance | yes | Aggregated performance metrics |
| ci_notes | string | no | Latest CI Agent observation about this prompt |

**File location**: `prompts/library.json`

---

### PromptVersion

Embedded in PromptEntry.version_history.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| version | string | yes | Version string |
| date | string (ISO 8601 date) | yes | When this version was applied |
| file | string | yes | Repo-relative path to the archived prompt file |
| notes | string | yes | What changed in this version |
| applied_by | string | no | `ci_recommendation` (with recommendation_id) or `operator` |

**File location**: `prompts/versions/{agent}_{version}.md`

---

### PromptPerformance

Embedded in PromptEntry.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| avg_confidence_score | float | yes | Mean Validation Agent score across all runs using this prompt version |
| validation_pass_rate | float | yes | Proportion of runs where validation_pass=true |
| avg_latency_ms | integer | yes | Mean agent latency when using this prompt |
| avg_tokens_per_run | integer | yes | Mean total tokens when using this prompt |
| sample_size | integer | yes | Number of runs contributing to these metrics |
| last_evaluated | string (ISO 8601 date) | yes | Date of most recent CI evaluation |

---

### VaultMaintenanceRun

One record per Vault Maintenance Agent execution.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| maintenance_run_id | string | yes | Unique identifier |
| run_date | string (ISO 8601 UTC) | yes | When the maintenance run executed |
| auto_fixes | MaintenanceAutoFix[] | yes | List of changes applied without approval |
| proposals | MaintenanceProposal[] | yes | List of high-risk changes proposed for approval |
| report_path | string | yes | Vault path to the Markdown proposal report |
| commit_sha | string | no | Git commit SHA of the auto-fix commit (if any auto-fixes were applied) |

**File location**: `jarvis/vault/maintenance_{YYYY-MM-DD}.md` (proposals only; auto-fix changes are committed directly to git)

---

### MaintenanceAutoFix

Embedded in VaultMaintenanceRun.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| fix_type | string | yes | `broken_link`, `naming_violation`, `missing_frontmatter`, `empty_file` |
| file_path | string | yes | Vault-relative path to the file that was fixed |
| description | string | yes | What was changed |
| reversible | boolean | yes | Always true — auto-fixes are always git-reversible |

---

### MaintenanceProposal

Embedded in VaultMaintenanceRun.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| proposal_id | string | yes | Sequential identifier (e.g. `M-001`) |
| proposal_type | string | yes | `duplicate_note`, `stale_record`, `wrong_folder`, `merge_candidate` |
| affected_paths | string[] | yes | Vault-relative paths of the files involved |
| description | string | yes | Plain-English description of the issue and proposed action |
| risk_level | string | yes | Always `HIGH` for proposals (auto-fixes are always `LOW`) |
| approval_inbox_text | string | yes | Exact text the operator must put in the inbox to approve |
| status | string | yes | `pending`, `approved`, `rejected` |

---

### PRReview

Extends TaskResult from Phase 1. One per PR review request.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| task_id | string | yes | Inherited from TaskResult |
| pr_url | string | yes | The GitHub PR URL that was reviewed |
| pr_number | integer | yes | GitHub PR number |
| repo | string | yes | GitHub repo in `owner/name` format |
| change_summary | string | yes | Plain-English summary of what the PR changes |
| risk_assessment | string | yes | `HIGH`, `MED`, or `LOW` |
| concerns | string[] | yes | List of specific concerns: security, logic, performance |
| suggested_questions | string[] | yes | Questions the operator could ask the PR author |
| approval_recommendation | string | yes | `APPROVE`, `REQUEST_CHANGES`, `NEEDS_MORE_CONTEXT` |
| human_review_required | boolean | yes | Always true for PR reviews |
| vault_path | string | yes | Path where this review was written in the vault |

---

## State Transitions

### AgentLogEntry.status
```
pending → in_progress → success
                     → partial    (validation score 0.60–0.89 accepted after retry)
                     → skipped    (validation score < 0.60, or unrecoverable error)
                     → failed     (Validation Agent crash handled gracefully)
```

### CIRecommendation.recommendation_status
```
pending → approved → applied
       → rejected
         applied → rolled_back
```

### PromptEntry.status
```
draft → approved
     → testing
approved → deprecated
testing  → approved
         → deprecated
```

### MaintenanceProposal.status
```
pending → approved
        → rejected
```
