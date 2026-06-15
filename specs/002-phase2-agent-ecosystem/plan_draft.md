# Jarvis Phase 2 — Architecture & Implementation Plan

**Feature ID**: 002-jarvis-phase2  
**Status**: Draft  
**Created**: 2026-06-14  
**Derived from**: Grilling session on Phase 2 design decisions

---

## Decisions Summary

| Decision | Choice |
|---|---|
| Log storage | JSON flat files in vault, synced via existing Power Automate |
| pm_workflow integration | Jarvis writes downstream to same SharePoint structure; absorbs in Phase 3+ |
| Monitoring location | Embedded in `orchestrator/main.py` |
| Recovery mode | Skip and continue degraded; partial TaskResult |
| CI trigger | Bi-weekly: Sunday + Wednesday nights (GitHub Actions cron) |
| CI approval | Inbox task → Jarvis applies on next run |
| Prompt library | `prompts/` repo dir + `prompts/library.json` metadata index |
| New agents | Validation, PR Review, CI, Vault Maintenance |
| Vault Maint scope | Auto-fix low-risk (links, naming); propose high-risk via inbox |
| Confidence thresholds | ≥0.90 pass / 0.60–0.89 retry once / <0.60 escalate; self-calibrating |
| Build sequence | Logging → Validation → CI → Vault Maint → PR Review |

---

## 1. Architecture Overview

```
TRIGGER SOURCES
  ├── GitHub Actions cron (11PM weeknights, biweekly CI Sunday/Wednesday)
  ├── Inbox commit push
  └── Manual workflow_dispatch

ORCHESTRATION LAYER (orchestrator/main.py)
  ├── Inbox Parser
  ├── PII Guard
  ├── Vault Reader (context retrieval)
  ├── [NEW] Monitoring Wrapper (retry/skip logic embedded here)
  └── Agent Router

AGENTS
  Existing:
  ├── Orchestrator Agent    (claude-sonnet-4-6)
  ├── Research Agent        (claude-haiku-4-5)
  ├── GCP Discovery Agent   (claude-haiku-4-5, daytime only)
  └── Obsidian Writer Agent (claude-haiku-4-5)

  New Phase 2:
  ├── Validation Agent      (claude-haiku-4-5) ← runs after each agent, scores output
  ├── CI Agent              (claude-sonnet-4-6) ← biweekly batch, reads JSON logs
  ├── Vault Maintenance     (claude-haiku-4-5) ← weekly, analyzes vault structure
  └── PR Review Agent       (claude-sonnet-4-6) ← triggered by inbox task

STORAGE LAYER
  Existing (Markdown):
  ├── jarvis/tasks/{task_id}.md
  ├── jarvis/digests/{date}.md
  └── jarvis/agents/{agent}-lessons.md

  New Phase 2 (JSON):
  ├── jarvis/logs/{date}/{run_id}.json     ← structured agent execution logs
  ├── jarvis/ci/ci_report_{date}.md        ← CI Agent output (human-readable)
  ├── jarvis/ci/ci_scores_{date}.json      ← CI scoring data (machine-readable)
  └── jarvis/vault/maintenance_{date}.md   ← Vault Maintenance report

PROMPT LIBRARY
  prompts/
  ├── orchestrator.md, research.md, etc.   ← unchanged
  ├── library.json                          ← [NEW] metadata index
  └── versions/                             ← [NEW] archived prompt versions

OUTPUT PIPELINE (unchanged)
  Power Automate webhook → SharePoint → OneDrive → Obsidian vault
  ↑ Now also syncs JSON log files to SharePoint (same webhook, new file paths)

PM_WORKFLOW INTEGRATION
  pm_workflow (PowerShell) → SharePoint document library (path: PM/)
  Jarvis → same SharePoint library (path: Jarvis/)
  Phase 3+: CI Agent identifies overlap → proposes absorption of classification logic
```

---

## 2. Agent Ecosystem Design

### Existing Agents (Phase 2 Changes)

**Orchestrator Agent** — gains monitoring wrapper; logs to JSON after each run  
**Research Agent** — output scored by Validation Agent before added to TaskResult  
**GCP Discovery Agent** — output scored; skip-and-degrade on failure  
**Obsidian Writer Agent** — writes new JSON log files alongside existing Markdown outputs

---

### New: Validation Agent

**Purpose**: Score every agent output for quality, completeness, and compliance before it is committed to the TaskResult.

**Model**: `claude-haiku-4-5`

**Trigger**: Inline, after every agent completes in the pipeline

**Inputs**:
- Agent name and output dict
- Task context (original request)
- Historical score baseline for this agent (from `library.json` or recent JSON logs)

**Output schema**:
```json
{
  "agent_name": "research",
  "run_id": "run_20260614_001",
  "confidence_score": 0.87,
  "pass": true,
  "retry_recommended": false,
  "escalate": false,
  "quality_dimensions": {
    "relevance": 0.92,
    "completeness": 0.85,
    "compliance": 1.00,
    "format_adherence": 0.80
  },
  "notes": "Output complete but context window felt thin."
}
```

**Threshold logic**:
```
score ≥ 0.90        → accept, continue
0.60 ≤ score < 0.90 → retry agent once; accept if retry score ≥ 0.85
score < 0.60        → skip agent, mark partial, add to digest as [HUMAN REVIEW REQUIRED]
```

**Self-calibration**: When 20+ data points exist for an agent, CI Agent evaluates whether thresholds should shift and proposes adjustment via CI report.

**Failure mode**: If Validation Agent itself crashes → treat agent output as passing (0.90 assumed) and log Validation Agent failure separately. Never block task completion.

---

### New: CI Agent

**Purpose**: Analyze structured JSON logs across two run cycles, identify improvement opportunities, score proposed changes, and produce a human-readable report for inbox-task-driven approval.

**Model**: `claude-sonnet-4-6`

**Trigger**: GitHub Actions cron — `0 23 * * 0,3` (11PM Sunday and Wednesday)

**Inputs**:
- `jarvis/logs/**/*.json` — all structured run logs since last CI run
- `prompts/library.json` — current prompt metadata and scores
- `jarvis/ci/ci_scores_{last_run}.json` — previous CI baseline

**CI Scoring dimensions**:

| Dimension | Weight | Data Source |
|---|---|---|
| Success rate | 25% | `status` field across logs |
| Output quality | 20% | Validation Agent `confidence_score` |
| Validation pass rate | 15% | Validation Agent `pass` counts |
| Token efficiency | 15% | `token_usage` per task/output length |
| Latency | 10% | `latency_ms` per agent |
| Recovery rate | 10% | Retry-to-success ratio |
| Human intervention rate | 5% | `escalation_flag` counts |

**CI Score formula**:
```
CI_score = (success_rate × 0.25) + (output_quality × 0.20) +
           (validation_pass_rate × 0.15) + (token_efficiency × 0.15) +
           (1 - normalized_latency × 0.10) + (recovery_rate × 0.10) +
           (1 - human_intervention_rate × 0.05)
```

**Recommendation thresholds**:
- CI_score improvement ≥ 15% → **Recommend improvement** (propose for inbox approval)
- CI_score improvement 5–14% → **Recommend testing** (flag low-confidence, require A/B run)
- CI_score improvement < 5% → **Reject** (noise; discard)

**Outputs**:
- `jarvis/ci/ci_report_{YYYY-MM-DD}.md` — human-readable, synced to SharePoint
- `jarvis/ci/ci_scores_{YYYY-MM-DD}.json` — machine-readable for next CI cycle

**Recommendation format**:
```markdown
## Recommendation R-001
**Type**: Prompt Improvement
**Agent**: research
**Current prompt**: prompts/research.md (v1.2)
**Proposed change**: Expand vault search to include /knowledge/** in addition to /tasks/**
**Evidence**: 
  - 4 of 6 runs had research confidence_score 0.61–0.74 (retry window)
  - Vault notes in /knowledge/ matched task keywords in 3 cases but weren't retrieved
**CI Score delta**: +18.3% (0.74 → 0.87 projected)
**Risk level**: LOW
**To approve**: Commit inbox task "apply CI recommendation R-001"
**To reject**: No action needed — recommendation expires after next CI run
```

**Approval flow**: Operator writes `Apply CI recommendation R-001` in inbox → Jarvis detects CI approval task type → reads `ci_scores_{date}.json` → applies the specific change → commits → updates `library.json`.

---

### New: Vault Maintenance Agent

**Purpose**: Analyze Obsidian vault structure, enforce organization standards, and surface cleanup opportunities.

**Model**: `claude-haiku-4-5`

**Trigger**: GitHub Actions cron — `0 22 * * 6` (10PM Saturday)

**Auto-fix (no approval needed)**:
- Broken internal wikilinks
- Filename convention violations (rename to kebab-case)
- Missing frontmatter fields (`created`, `last_updated`)
- Orphaned empty files (0 content lines)

**Propose for approval (inbox task required)**:
- Duplicate knowledge notes covering the same topic
- Stale task records (> 90 days old, no references)
- Notes in wrong folder based on content classification
- Merge candidates

**Outputs**:
- Auto-fix changes committed directly (commit: `vault: maintenance auto-fix [jarvis-skip]`)
- `jarvis/vault/maintenance_{YYYY-MM-DD}.md` — proposals requiring human approval

**Failure mode**: Any file write error → abort all writes, log error, produce report-only output.

---

### New: PR Review Agent

**Purpose**: Analyze GitHub pull requests and produce structured review summaries. Triggered manually via inbox task.

**Model**: `claude-sonnet-4-6`

**Trigger**: Inbox task with `agents: pr_review` and a GitHub PR URL or PR number

**Inputs**:
- PR diff (GitHub API, read-only `GITHUB_TOKEN`)
- PR description and comments
- Relevant vault knowledge notes (surfaced by Research Agent)

**Output**: `jarvis/tasks/{task_id}.md` with structured review:
- Summary of changes
- Risk assessment (HIGH/MED/LOW)
- Specific concerns (security, logic, performance)
- Suggested questions for PR author
- Approval recommendation
- All flagged `[HUMAN REVIEW REQUIRED]`

**Hard constraint**: Never post comments to GitHub. `GITHUB_TOKEN` must be read-only (`repo:read` scope). No `PATCH`/`POST` calls to GitHub API.

**New secret required**: `GITHUB_TOKEN` in GitHub Actions

---

## 3. Monitoring & Logging Design

### Structured JSON Log Schema

Every agent execution emits one JSON record appended to `jarvis/logs/{YYYY-MM-DD}/{run_id}.json`.

**Required fields**:
```json
{
  "timestamp": "2026-06-14T23:14:32Z",
  "run_id": "run_20260614_001",
  "trace_id": "trace_abc123",
  "workflow_id": "overnight_task",
  "agent_name": "research",
  "agent_version": "1.0.0",
  "status": "success",
  "latency_ms": 3241,
  "token_usage": {
    "input": 1840,
    "output": 412,
    "total": 2252,
    "estimated_cost_usd": 0.0024
  }
}
```

**Optional fields** (included when relevant):
```json
{
  "prompt_id": "research_v1.2",
  "prompt_version": "1.2",
  "trigger_source": "github_actions_cron",
  "input_summary": "...",
  "output_summary": "...",
  "confidence_score": 0.87,
  "validation_pass": true,
  "tool_calls": ["vault_reader.search_notes"],
  "error_type": null,
  "retry_count": 0,
  "fallback_target": null,
  "escalation_flag": false,
  "human_review_required": false,
  "partial_run": false,
  "skip_reason": null
}
```

**Sample — successful execution**:
```json
{
  "timestamp": "2026-06-14T23:14:32Z",
  "run_id": "run_20260614_001",
  "trace_id": "trace_abc123",
  "workflow_id": "overnight_task",
  "agent_name": "research",
  "agent_version": "1.0.0",
  "status": "success",
  "latency_ms": 3241,
  "token_usage": {"input": 1840, "output": 412, "total": 2252, "estimated_cost_usd": 0.0024},
  "prompt_id": "research_v1.2",
  "confidence_score": 0.91,
  "validation_pass": true,
  "retry_count": 0,
  "escalation_flag": false,
  "human_review_required": false
}
```

**Sample — retry after transient failure**:
```json
{
  "timestamp": "2026-06-14T23:18:05Z",
  "run_id": "run_20260614_001",
  "trace_id": "trace_abc123",
  "workflow_id": "overnight_task",
  "agent_name": "gcp_discovery",
  "agent_version": "1.0.0",
  "status": "success",
  "latency_ms": 8902,
  "token_usage": {"input": 920, "output": 310, "total": 1230, "estimated_cost_usd": 0.0013},
  "prompt_id": "gcp_discovery_v1.0",
  "confidence_score": 0.88,
  "validation_pass": true,
  "error_type": "api_timeout",
  "retry_count": 1,
  "escalation_flag": false,
  "human_review_required": false
}
```

**Sample — escalation after validation failure**:
```json
{
  "timestamp": "2026-06-14T23:22:41Z",
  "run_id": "run_20260614_001",
  "trace_id": "trace_abc123",
  "workflow_id": "overnight_task",
  "agent_name": "obsidian_writer",
  "agent_version": "1.0.0",
  "status": "partial",
  "latency_ms": 11200,
  "token_usage": {"input": 2100, "output": 890, "total": 2990, "estimated_cost_usd": 0.0032},
  "prompt_id": "obsidian_writer_v1.1",
  "confidence_score": 0.54,
  "validation_pass": false,
  "retry_count": 1,
  "escalation_flag": true,
  "human_review_required": true,
  "skip_reason": "validation_score_below_threshold",
  "fallback_target": "human_review",
  "partial_run": true
}
```

### Error Classification Model

| Class | Examples | Recovery |
|---|---|---|
| `api_timeout` | Anthropic 529, request timeout | Retry once, then skip-degrade |
| `api_rate_limit` | HTTP 429 | Retry 30s backoff (up to 3x), then skip-degrade |
| `validation_fail` | confidence < 0.60 after retry | Skip-degrade, escalate to digest |
| `pii_detected` | Name/email in output | Block output, flag `needs_clarification` |
| `config_missing` | `gcp.project` not set | Skip agent, log warning |
| `parse_error` | Malformed agent response | Skip agent, log raw output in lessons file |
| `tool_error` | `bq ls` subprocess fails | Skip GCP agent, degrade |
| `webhook_fail` | Power Automate non-200 after 3 retries | Write to `run-errors.log`, alert in next digest |

---

## 4. Prompt Library Architecture

### `prompts/library.json` schema

```json
{
  "schema_version": "1.0",
  "last_updated": "2026-06-14T23:00:00Z",
  "prompts": [
    {
      "prompt_id": "research_v1.2",
      "title": "Research Agent — Vault Context Retrieval",
      "file": "prompts/research.md",
      "linked_agent": "research",
      "use_case": "Retrieve relevant vault context before Anthropic API call",
      "tags": ["research", "context", "vault", "cache"],
      "status": "approved",
      "version": "1.2",
      "version_history": [
        {"version": "1.0", "date": "2026-05-01", "file": "prompts/versions/research_v1.0.md", "notes": "Initial"},
        {"version": "1.1", "date": "2026-05-20", "file": "prompts/versions/research_v1.1.md", "notes": "Added cache hit instruction"},
        {"version": "1.2", "date": "2026-06-01", "file": "prompts/versions/research_v1.2.md", "notes": "Tightened output format"}
      ],
      "performance": {
        "avg_confidence_score": 0.84,
        "validation_pass_rate": 0.79,
        "avg_latency_ms": 3100,
        "avg_tokens_per_run": 2100,
        "sample_size": 12,
        "last_evaluated": "2026-06-11"
      },
      "ci_notes": "Validation flagged 3 of 12 runs in retry window. CI R-001 proposes expanding vault search scope."
    },
    {
      "prompt_id": "orchestrator_v1.0",
      "title": "Orchestrator Agent — Task Routing",
      "file": "prompts/orchestrator.md",
      "linked_agent": "orchestrator",
      "use_case": "Parse inbox task and determine agent routing",
      "tags": ["orchestrator", "routing", "classification"],
      "status": "approved",
      "version": "1.0",
      "version_history": [
        {"version": "1.0", "date": "2026-05-01", "file": "prompts/versions/orchestrator_v1.0.md", "notes": "MVP baseline"}
      ],
      "performance": {
        "avg_confidence_score": 0.93,
        "validation_pass_rate": 0.92,
        "avg_latency_ms": 4800,
        "avg_tokens_per_run": 3200,
        "sample_size": 12,
        "last_evaluated": "2026-06-11"
      },
      "ci_notes": "Strong performer. No recommendations pending."
    },
    {
      "prompt_id": "gcp_discovery_v1.0",
      "title": "GCP Discovery Agent — Dataset Enumeration",
      "file": "prompts/gcp_discovery.md",
      "linked_agent": "gcp_discovery",
      "use_case": "Enumerate BigQuery datasets and translate to plain English",
      "tags": ["gcp", "bigquery", "discovery", "readonly"],
      "status": "approved",
      "version": "1.0",
      "version_history": [
        {"version": "1.0", "date": "2026-05-15", "file": "prompts/versions/gcp_discovery_v1.0.md", "notes": "MVP baseline"}
      ],
      "performance": {
        "avg_confidence_score": 0.88,
        "validation_pass_rate": 0.85,
        "avg_latency_ms": 6200,
        "avg_tokens_per_run": 1800,
        "sample_size": 4,
        "last_evaluated": "2026-06-11"
      },
      "ci_notes": "Low sample size (daytime-only). Confidence pending more runs."
    }
  ]
}
```

### Versioning and Approval Flow

1. CI Agent proposes prompt change in `ci_report_{date}.md` with full diff
2. Operator approves via inbox task: `apply CI recommendation R-001`
3. Jarvis detects CI approval type → copies current prompt to `prompts/versions/{agent}_v{old}.md` → writes new prompt → bumps `library.json` version, status=`approved`
4. Next run uses new prompt; Validation Agent scores it
5. If new prompt underperforms, CI Agent flags regression and proposes revert in next bi-weekly report

---

## 5. Orchestration Strategy

### Fallback Decision Tree

```
AGENT EXECUTION ATTEMPT
        │
        ▼
   Run agent
        │
   ┌────▼────┐
   │ Success? │
   └────┬─────┘
        │ No
        ▼
   Classify error
        │
   ┌────▼──────────────────┐
   │ Transient?             │
   │ (timeout, rate limit)  │
   └────┬───────────────────┘
        │ Yes → RETRY (1x, 30s backoff)
        │ No ↓
        ▼
   Run Validation Agent on output
        │
   ┌────▼────────────────────────────┐
   │ confidence_score ≥ 0.90?        │
   └────┬────────────────────────────┘
        │ Yes → ACCEPT, continue
        │ No ↓
   ┌────▼────────────────────────────┐
   │ confidence_score 0.60–0.89?     │
   └────┬────────────────────────────┘
        │ Yes → RETRY AGENT ONCE
        │         ├─ If retry score ≥ 0.60 → ACCEPT (partial)
        │         └─ If retry score < 0.60 → SKIP ↓
        │ No (< 0.60) ↓
        ▼
   SKIP AGENT
   Mark agent_run.status = "skipped"
   Add to digest [HUMAN REVIEW REQUIRED]
   TaskResult.status = "partial"
   Log JSON with escalation_flag=true
        │
        ▼
   Continue to next agent
```

### Fallback Hierarchy

| Stage | Trigger | Action |
|---|---|---|
| **Retry** | Transient error (timeout, 429) | Retry once with 30s backoff |
| **Validate** | Any agent completion | Validation Agent scores output |
| **Retry (quality)** | confidence 0.60–0.89 | Re-run agent with same prompt |
| **Degrade** | confidence < 0.60 after retry | Skip agent, mark partial |
| **Escalate** | escalation_flag=true | Add to digest for human review |
| **Human** | `needs_clarification` status | Operator must respond via inbox |

### Workflow Example 1: Research Agent Retry Path

```
Task: "Summarize GCP cost anomalies from last quarter"

1. Research Agent runs
   → API timeout (error_type: api_timeout)
   → RETRY after 30s
   → Second call succeeds
   → Validation Agent: confidence_score = 0.83 (retry window)
   → RETRY Research Agent once more
   → Validation Agent: confidence_score = 0.91
   → ACCEPT
   → Log: retry_count=2, status=success, confidence=0.91

2. Continue to GCP Discovery, Obsidian Writer
3. Task completes as "completed" (not partial)
```

### Workflow Example 2: Obsidian Writer Escalation Path

```
Task: "Draft weekly status email"

1. Orchestrator routes to: research, obsidian
2. Research runs successfully (confidence=0.92)
3. Obsidian Writer runs
   → PII detected in draft (recipient name in output)
   → pii_guard.sanitize_text() strips name
   → Validation Agent: confidence_score = 0.55 (below 0.60)
   → RETRY Obsidian Writer
   → Validation Agent: confidence_score = 0.52
   → SKIP, escalation_flag=true

4. TaskResult.status = "partial"
5. Digest entry: [HUMAN REVIEW REQUIRED] — obsidian_writer skipped, confidence 0.52
6. JSON log: escalation_flag=true, human_review_required=true
7. Operator reviews next morning, manually handles the draft
```

---

## 6. pm_workflow Integration

### Background
`pm_workflow` is a set of PowerShell scripts that scrape Outlook and SharePoint, classify inbound emails, and write briefs/tracking logs to a SharePoint document library under `PM/`.

### Phase 2 Integration
Jarvis writes outputs to the **same SharePoint library** under a parallel path (`Jarvis/`). No changes to pm_workflow scripts. Both systems share the library; operator sees both in SharePoint/Obsidian.

**Settings update required** (`config/settings.yaml`):
```yaml
power_automate:
  sharepoint_site_url: "{your-site-url}"
  document_library: "{library-name}"
  pm_workflow_root: "PM"      # existing pm_workflow output path (read-only reference)
  jarvis_root: "Jarvis"       # Jarvis Phase 2 output path
```

### Phase 3+ (out of scope)
CI Agent identifies overlap between pm_workflow classification and Jarvis Research Agent outputs → proposes a new Email Classification Agent that absorbs the PowerShell scraping logic → pm_workflow scripts deprecated over time.

---

## 7. Implementation Roadmap

### Sprint 1 — Structured Logging Foundation (Weeks 1–2)

**Goal**: Every agent run emits a structured JSON log. Zero behavior changes.

- [ ] Create `orchestrator/utils/run_logger.py` — emit JSON record per agent per run
- [ ] Add `run_id` and `trace_id` generation to `main.py` (UUID4, passed to all agents)
- [ ] Update `token_logger.py` to write to `jarvis/logs/{date}/{run_id}.json`
- [ ] Update Power Automate webhook payload to include JSON log files in `files[]`
- [ ] Add `agent_version` field to each agent (hardcoded string, e.g. `"1.0.0"`)
- [ ] Test: confirm JSON logs appear in SharePoint after a run

---

### Sprint 2 — Validation Agent (Weeks 3–4)

**Goal**: Every agent output is scored before being accepted into TaskResult.

- [ ] Create `orchestrator/agents/validation.py` — scores output dict, returns ValidationResult
- [ ] Add Validation Agent to `main.py` pipeline (inline, after each agent)
- [ ] Implement three-tier threshold logic (0.90 / 0.60 / below)
- [ ] Add `confidence_score`, `validation_pass`, `retry_count` to JSON log schema
- [ ] Update Obsidian Writer to include validation scores in task record Markdown
- [ ] Test: force a low-confidence output (mock), confirm skip-and-degrade behavior

---

### Sprint 3 — CI Agent + Prompt Library (Weeks 5–7)

**Goal**: Bi-weekly analysis of JSON logs produces actionable recommendations.

- [ ] Initialize `prompts/library.json` with entries for all 4 existing prompts
- [ ] Create `prompts/versions/` and archive current prompts as v1.0
- [ ] Create `orchestrator/agents/ci_agent.py` — reads JSON logs, scores dimensions, generates report
- [ ] Add CI Agent cron to `.github/workflows/jarvis.yml` (`0 23 * * 0,3`)
- [ ] Build CI report Markdown template (`jarvis/ci/ci_report_{date}.md`)
- [ ] Implement inbox handler: detect `apply CI recommendation R-{id}` → apply change
- [ ] Test: run CI Agent on 5 synthetic log files, confirm report format and scoring

---

### Sprint 4 — Vault Maintenance Agent (Weeks 8–9)

**Goal**: Weekly vault cleanup with auto-fix for low-risk issues.

- [ ] Create `orchestrator/agents/vault_maintenance.py`
- [ ] Implement auto-fix: broken links, naming conventions, missing frontmatter, empty files
- [ ] Implement proposal generation: duplicates, stale notes, merge candidates
- [ ] Add Vault Maintenance cron to `.github/workflows/jarvis.yml` (`0 22 * * 6`)
- [ ] Write auto-fix changes with commit `vault: maintenance auto-fix [jarvis-skip]`
- [ ] Output proposal report to `jarvis/vault/maintenance_{date}.md`

---

### Sprint 5 — PR Review Agent (Weeks 10–11)

**Goal**: On-demand PR analysis via inbox task.

- [ ] Add `GITHUB_TOKEN` secret to GitHub Actions (read-only, `repo:read`)
- [ ] Create `orchestrator/agents/pr_review.py` — fetch diff, analyze, produce review
- [ ] Update inbox parser to recognize `agents: pr_review` and extract PR URL/number
- [ ] Update Orchestrator Agent routing to handle `pr_review` agent type
- [ ] Test: submit inbox task with a real PR URL, confirm review lands in vault

---

## 8. New Files and Directories

```
jarvis_project/
├── orchestrator/
│   ├── agents/
│   │   ├── validation.py          [NEW Sprint 2]
│   │   ├── ci_agent.py            [NEW Sprint 3]
│   │   ├── vault_maintenance.py   [NEW Sprint 4]
│   │   └── pr_review.py           [NEW Sprint 5]
│   └── utils/
│       └── run_logger.py          [NEW Sprint 1]
├── prompts/
│   ├── library.json               [NEW Sprint 3]
│   └── versions/                  [NEW Sprint 3]
│       ├── orchestrator_v1.0.md
│       ├── research_v1.0.md
│       ├── gcp_discovery_v1.0.md
│       └── obsidian_writer_v1.0.md
└── jarvis/
    ├── logs/                      [NEW Sprint 1]
    │   └── {date}/
    │       └── {run_id}.json
    ├── ci/                        [NEW Sprint 3]
    │   ├── ci_report_{date}.md
    │   └── ci_scores_{date}.json
    └── vault/                     [NEW Sprint 4]
        └── maintenance_{date}.md
```

---

## 9. Risks & Gaps

| Risk | Severity | Mitigation |
|---|---|---|
| JSON log volume growth | LOW | ~40 records/week at steady state. Negligible size for flat files. |
| Validation Agent scoring drift | MED | Self-calibration requires CI oversight. CI catches miscalibration in bi-weekly report. |
| CI has too little data on Wednesdays | MED | Wednesday run analyzes 2–3 overnight runs. Auto-raise recommendation threshold to 20% improvement on < 5 run cycles. |
| Prompt library version confusion | MED | `library.json` is single source of truth. Git history is the audit trail. CI Agent never modifies `library.json` directly. |
| Vault Maintenance auto-fix breaks content | MED | Auto-fix limited to links, naming, empty files — all reversible via git. Never touches content of non-empty notes without proposal approval. |
| pm_workflow SharePoint path conflict | LOW | Distinct root paths (`PM/` vs `Jarvis/`). No shared filenames. |
| PR Review Agent leaks code to GitHub | HIGH | `GITHUB_TOKEN` is read-only. No write scope. Code reviewed to confirm no `PATCH`/`POST` calls to GitHub API. |
| GCP service account still pending | MED | Daytime-only runs unblocked (operator auth). Service account is a Phase 3 dependency for overnight GCP runs. |
| CI Agent recommends a regression | MED | Rollback path: every applied change is a git commit. If Validation scores drop, CI flags regression and proposes revert in next cycle. |
