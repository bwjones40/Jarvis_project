# Implementation Plan: Jarvis Phase 2 — Agent Ecosystem Expansion

**Feature**: 003-phase2-agent-ecosystem
**Created**: 2026-06-14
**Spec**: [spec.md](spec.md)
**Data Model**: [data-model.md](data-model.md)
**Contracts**: [contracts/](contracts/)
**Quickstart**: [quickstart.md](quickstart.md)
**Architecture reference**: [specs/002-jarvis-phase2/plan.md](../002-jarvis-phase2/plan.md)

---

## Technical Context

| Item | Value |
|------|-------|
| Language | Python 3.12 |
| Runtime | GitHub Actions (ubuntu-latest, ephemeral) |
| Approved dependencies | `anthropic`, `google-cloud-bigquery`, `requests`, `pyyaml` (all existing) |
| New dependency | None — GitHub API calls use `requests` (already approved) |
| New secret | `GITHUB_TOKEN` (read-only, `repo:read` scope) — Sprint 5 only |
| New cron schedules | CI Agent: `0 23 * * 0,3` (Sun/Wed 11PM); Vault Maintenance: `0 22 * * 6` (Sat 10PM) |
| Existing models | Orchestrator: `claude-sonnet-4-6`; Subagents: `claude-haiku-4-5` |
| New agent models | Validation: `claude-haiku-4-5`; CI Agent: `claude-sonnet-4-6`; Vault Maintenance: `claude-haiku-4-5`; PR Review: `claude-sonnet-4-6` |

---

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| No PII | PASS | All new agents inherit PII guard; `input_summary`/`output_summary` in logs must not contain PII |
| No auto-send | PASS | PR Review Agent never calls GitHub write APIs; all output is vault-only |
| No auto-deploy CI changes | PASS | CI Agent is recommendation-only; inbox approval required for every change |
| Read-only GCP | PASS | No new GCP operations in Phase 2 |
| Approved services only | PASS | No new packages; GitHub API via `requests` (already approved) |
| Human approval for high-risk vault changes | PASS | Vault Maintenance proposals require inbox approval; auto-fix limited to reversible low-risk operations |

---

## Phase 0: Research

All decisions resolved. See [research.md](research.md) for full decision log.

**Key resolved decisions**:
- Log storage: JSON flat files in vault, existing Power Automate webhook
- Recovery mode: skip and continue degraded
- CI trigger: bi-weekly Sunday + Wednesday 11PM
- Confidence thresholds: ≥0.90 / 0.60–0.89 (retry) / <0.60 (skip)
- Build sequence: Logging → Validation → CI → Vault Maint → PR Review

---

## Phase 1: Sprint Plans

### Sprint 1 — Structured Logging Foundation (Weeks 1–2)

**Deliverable**: Every agent run emits a structured JSON log file synced to SharePoint.

**New files**:
- `orchestrator/utils/run_logger.py`

**Modified files**:
- `orchestrator/main.py` — generate `run_id`/`trace_id`, call `run_logger` after each agent
- `orchestrator/utils/token_logger.py` — integrate with run_logger (share token data)
- `orchestrator/utils/power_automate.py` — include JSON log files in webhook payload
- `orchestrator/agents/*.py` — add `agent_version = "1.0.0"` constant to each agent file
- `config/settings.yaml` — add `logging:` section with `log_dir: "jarvis/logs"`

**`run_logger.py` responsibilities**:
- `start_run(workflow_id, trigger_source, task_id=None) -> RunContext` — generates UUID4 `run_id` + `trace_id`, creates JSON file
- `log_agent_entry(run_context, agent_entry: dict)` — appends one `AgentLogEntry` to the JSON file
- `finalize_run(run_context, overall_status)` — writes `completed_at` and `overall_status` to the `run` object

**Validation**: See [quickstart.md Sprint 1 scenarios](quickstart.md#sprint-1-structured-logging)

---

### Sprint 2 — Validation Agent (Weeks 3–4)

**Deliverable**: Every subagent output is scored before being committed to TaskResult. Retry and skip-degrade logic is live.

**New files**:
- `orchestrator/agents/validation.py`
- `prompts/validation.md`

**Modified files**:
- `orchestrator/main.py` — call Validation Agent after each subagent; implement three-tier decision logic; update TaskResult.status to `partial` on skip
- `orchestrator/utils/run_logger.py` — add `confidence_score`, `validation_pass`, `retry_count` fields to `log_agent_entry`

**`validation.py` responsibilities**:
- `score_output(agent_name, output_dict, task_context, run_id) -> ValidationResult`
- Composite score formula: `(relevance × 0.35) + (completeness × 0.30) + (compliance × 0.25) + (format_adherence × 0.10)`
- Crash handling: return synthetic pass (0.90) and log Validation Agent failure separately
- See [contracts/validation-result-schema.md](contracts/validation-result-schema.md) for full schema

**Retry logic in `main.py`**:
```
score = validation.score_output(agent_name, output, task, run_id)
if score.confidence_score >= 0.90:
    accept(output)
elif score.confidence_score >= 0.60:
    retry_output = run_agent_again(agent)
    retry_score = validation.score_output(...)
    if retry_score.confidence_score >= 0.60:
        accept(retry_output, partial=True)
    else:
        skip_agent(agent, escalation_flag=True)
else:
    skip_agent(agent, escalation_flag=True)
```

**Validation**: See [quickstart.md Sprint 2 scenarios](quickstart.md#sprint-2-validation-agent)

---

### Sprint 3 — CI Agent + Prompt Library (Weeks 5–7)

**Deliverable**: Bi-weekly CI analysis produces scored recommendations. Prompt library is initialized. Inbox approval flow applies changes.

**New files**:
- `orchestrator/agents/ci_agent.py`
- `prompts/ci_agent.md`
- `prompts/library.json` (initialized with 4 existing prompt entries)
- `prompts/versions/orchestrator_v1.0.md` (archived copy)
- `prompts/versions/research_v1.0.md` (archived copy)
- `prompts/versions/gcp_discovery_v1.0.md` (archived copy)
- `prompts/versions/obsidian_writer_v1.0.md` (archived copy)

**Modified files**:
- `.github/workflows/jarvis.yml` — add CI Agent cron job (`0 23 * * 0,3`)
- `orchestrator/main.py` — add CI approval task handler (detect `apply CI recommendation R-{id}`)
- `orchestrator/utils/inbox_parser.py` — recognize `agents: ci_approval` task type

**`ci_agent.py` responsibilities**:
- `analyze_logs(log_dir, since_date) -> list[AgentLogEntry]` — reads all JSON logs in window
- `score_agents(entries) -> list[AgentScore]` — computes 7-dimension composite scores
- `generate_recommendations(scores, library) -> list[CIRecommendation]` — filters by threshold
- `write_report(ci_run, report_path, scores_path)` — writes Markdown report + JSON scores
- `update_library_performance(library_path, agent_scores)` — updates `performance` fields in library.json

**CI approval handler in `main.py`**:
- Detect task title matching `apply CI recommendation R-{id}`
- Load latest CI scores JSON
- Find recommendation by ID
- Apply the change (prompt swap OR config value update)
- Archive old value to `prompts/versions/`
- Update `library.json`
- Write task record confirming what was applied

**See schemas**: [contracts/ci-report-schema.md](contracts/ci-report-schema.md), [contracts/prompt-library-schema.md](contracts/prompt-library-schema.md)

**Validation**: See [quickstart.md Sprint 3 scenarios](quickstart.md#sprint-3-ci-agent-and-prompt-library)

---

### Sprint 4 — Vault Maintenance Agent (Weeks 8–9)

**Deliverable**: Weekly vault cleanup with auto-fix for low-risk issues and proposal reports for high-risk ones.

**New files**:
- `orchestrator/agents/vault_maintenance.py`
- `prompts/vault_maintenance.md`

**Modified files**:
- `.github/workflows/jarvis.yml` — add Vault Maintenance cron job (`0 22 * * 6`)
- `orchestrator/utils/inbox_parser.py` — recognize `agents: vault_approval` task type
- `orchestrator/main.py` — add vault approval handler (detect `apply vault maintenance proposal M-{id}`)

**`vault_maintenance.py` responsibilities**:
- `scan_vault(vault_root) -> VaultScanResult` — finds all issues across all categories
- `apply_auto_fixes(fixes) -> list[MaintenanceAutoFix]` — applies low-risk changes, aborts all on error
- `generate_proposals(high_risk_issues) -> list[MaintenanceProposal]` — proposals for human approval
- `write_report(run, report_path)` — writes Markdown proposal report
- Commit auto-fixes with message: `vault: maintenance auto-fix [jarvis-skip]`

**Auto-fix categories** (no approval needed):
- `broken_link` — repair wikilinks to known vault paths
- `naming_violation` — rename to kebab-case if file path contains uppercase or spaces
- `missing_frontmatter` — add `created` and `last_updated` fields derived from file timestamps
- `empty_file` — delete files with 0 content lines (after confirming no inbound links)

**Proposal categories** (approval required):
- `duplicate_note` — cosine similarity > 0.85 between two notes' content
- `stale_record` — task records older than 90 days with 0 inbound links
- `wrong_folder` — content classification suggests a different folder
- `merge_candidate` — two notes that are subsets of each other

**See schema**: [contracts/maintenance-report-schema.md](contracts/maintenance-report-schema.md)

**Validation**: See [quickstart.md Sprint 4 scenarios](quickstart.md#sprint-4-vault-maintenance-agent)

---

### Sprint 5 — PR Review Agent (Weeks 10–11)

**Deliverable**: On-demand PR analysis triggered via inbox task; review written to vault only.

**New files**:
- `orchestrator/agents/pr_review.py`
- `prompts/pr_review.md`

**Modified files**:
- `.github/workflows/jarvis.yml` — add `GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}` env var to `run-jarvis` job
- `orchestrator/utils/inbox_parser.py` — recognize `agents: pr_review`; extract `pr_url` or `pr_number` + `repo` from request body
- `orchestrator/agents/orchestrator.py` — route `pr_review` to PR Review Agent

**`pr_review.py` responsibilities**:
- `fetch_pr(repo, pr_number, github_token) -> PRData` — GET `https://api.github.com/repos/{repo}/pulls/{number}` and `/files`
- `analyze_pr(pr_data, vault_context, task_context) -> PRReview` — produce structured review
- Never call any GitHub API method other than GET

**GitHub API calls (read-only only)**:
- `GET /repos/{owner}/{repo}/pulls/{pull_number}` — PR metadata
- `GET /repos/{owner}/{repo}/pulls/{pull_number}/files` — changed files and diffs

**Hard constraints**:
- No `POST`, `PATCH`, `PUT`, `DELETE` calls to GitHub API ever
- `GITHUB_TOKEN` env var must be checked at agent start; skip with `[HUMAN REVIEW REQUIRED: GITHUB_TOKEN not set]` if absent
- PR diff size limit: if total changed lines > 2000, analyze only the first 2000 lines and note the truncation

**See data model**: [data-model.md — PRReview entity](data-model.md#prreview)

**Validation**: See [quickstart.md Sprint 5 scenarios](quickstart.md#sprint-5-pr-review-agent)

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| JSON log volume outpaces Power Automate payload limit | LOW | ~8KB per run file; PA supports up to 100MB payloads |
| Validation Agent self-calibration converges wrong | MED | CI Agent monitors calibration drift; proposes threshold adjustment via recommendation |
| CI Agent recommends a change that regresses performance | MED | Every applied change is a git commit; CI flags regression in next cycle; rollback via inbox task |
| Vault Maintenance auto-fix corrupts a file | MED | Auto-fix aborts all writes on any error; git history provides full rollback |
| PR Review Agent accidentally gains write GitHub scope | HIGH | `GITHUB_TOKEN` must be scoped to `repo:read` only; code review to confirm no write API calls |
| Wednesday CI runs have insufficient sample data | MED | `low_sample_warning: true` raises recommendation threshold to 20%; suppress recommendations if < 3 runs |
| pm_workflow SharePoint path conflicts with Jarvis paths | LOW | `Jarvis/` root path is distinct from pm_workflow's `PM/` root; no shared filenames |
| prompt library.json diverges from actual prompt files | MED | CI Agent validates consistency between library entries and actual files on each run |

---

## Open Items

- SharePoint `Jarvis/` root path must be confirmed with the Power Automate flow owner before Sprint 1
- GCP service account IAM approval remains pending (Phase 3 dependency, not Phase 2)
- `GITHUB_TOKEN` org-level permissions must be confirmed before Sprint 5 begins
