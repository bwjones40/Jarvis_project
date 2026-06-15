# Quickstart: Jarvis Phase 2 Validation Guide

**Feature**: 003-phase2-agent-ecosystem
**Created**: 2026-06-14

Use these scenarios to validate each Phase 2 sprint end-to-end. Run them in order — each sprint builds on the previous.

---

## Prerequisites

All Phase 1 validation scenarios in `specs/001-jarvis-mvp/quickstart.md` must pass before beginning Phase 2 validation.

Required secrets in GitHub Actions:
- `ANTHROPIC_API_KEY` (existing)
- `POWER_AUTOMATE_WEBHOOK_URL` (existing)
- `GITHUB_TOKEN` (new — read-only, `repo:read` scope; required for Sprint 5 only)

---

## Sprint 1: Structured Logging

**Goal**: Confirm every agent run produces a structured JSON log file.

**Steps**:
1. Commit a valid task to `jarvis/inbox.md`
2. Wait for the GitHub Actions run to complete
3. Check SharePoint under `Jarvis/logs/{today's date}/` for a JSON file

**Expected outcome**:
- A file `{run_id}.json` exists in SharePoint
- The file contains a `run` object with `run_id`, `trace_id`, `workflow_id`, `overall_status`
- The file contains an `agents` array with one entry per agent that executed
- Each entry has `timestamp`, `agent_name`, `agent_version`, `status`, `latency_ms`, `token_usage`
- `overall_status` matches the task outcome (should be `completed` for a valid task)

**Failure indicators**:
- No JSON file in SharePoint → webhook payload not updated
- JSON file exists locally (`jarvis/logs/`) but not in SharePoint → Power Automate webhook not including log files

**Validation command** (run locally after pulling from SharePoint/OneDrive):
```bash
python - <<'PY'
import json
from pathlib import Path
from datetime import date

log_dir = Path(f"jarvis/logs/{date.today().isoformat()}")
files = list(log_dir.glob("*.json"))
assert files, f"No log files found in {log_dir}"
for f in files:
    data = json.loads(f.read_text())
    assert "run" in data
    assert "agents" in data
    assert len(data["agents"]) > 0
    for entry in data["agents"]:
        assert "run_id" in entry
        assert "agent_name" in entry
        assert "status" in entry
        assert "token_usage" in entry
print(f"PASS: {len(files)} log file(s) found and valid")
PY
```

---

## Sprint 2: Validation Agent

**Goal**: Confirm quality gates are live — outputs are scored and recovery logic fires.

### Scenario 2A: High-confidence pass

**Steps**:
1. Commit a well-formed, clear task to `jarvis/inbox.md`
2. Wait for the run to complete
3. Check the morning digest and the JSON log

**Expected outcome**:
- JSON log: all agent entries have `confidence_score ≥ 0.90` and `validation_pass: true`
- Digest: quality scores table visible (no `[HUMAN REVIEW REQUIRED]` for this run)
- `overall_status: completed`

### Scenario 2B: Forced low-confidence (skip and degrade)

**Steps**:
1. Modify the test environment to inject a synthetic Validation Agent score of 0.45 for `obsidian_writer` (use `--dry-run` or a test fixture)
2. Run the pipeline
3. Check the JSON log and digest

**Expected outcome**:
- JSON log: `obsidian_writer` entry has `status: skipped`, `escalation_flag: true`, `retry_count: 1`
- Digest: `[HUMAN REVIEW REQUIRED]` entry for `obsidian_writer`
- `overall_status: partial`
- Run did NOT halt — other agents completed normally

### Scenario 2C: Validation Agent failure (graceful)

**Steps**:
1. Simulate Validation Agent crash (e.g., bad prompt or forced exception in test)
2. Run the pipeline
3. Check the JSON log and digest

**Expected outcome**:
- Scored agent's output is treated as passing (synthetic 0.90 score in log)
- A separate JSON log entry for `validation` has `status: failed`
- Digest includes a warning about Validation Agent error
- Run completed normally — pipeline was NOT halted

---

## Sprint 3: CI Agent and Prompt Library

**Goal**: Confirm bi-weekly CI analysis produces actionable reports and the approval flow works.

### Scenario 3A: CI report generation

**Prerequisites**: At least 3 completed Jarvis overnight runs with JSON logs in `jarvis/logs/`

**Steps**:
1. Trigger the CI Agent manually via `workflow_dispatch` (selecting the CI workflow)
2. Wait for the run to complete
3. Check SharePoint for CI report

**Expected outcome**:
- `jarvis/ci/ci_report_{today}.md` exists in SharePoint
- `jarvis/ci/ci_scores_{today}.json` exists in SharePoint
- Report contains per-agent composite scores
- At least one recommendation appears (or a note that insufficient data prevents recommendations)
- Each recommendation includes `approval_inbox_text`

### Scenario 3B: Prompt Library initialization

**Steps**:
1. Verify `prompts/library.json` exists in the repo
2. Check that all 4 existing agents have entries (`orchestrator`, `research`, `gcp_discovery`, `obsidian_writer`)
3. Check `prompts/versions/` for archived v1.0 copies

**Expected outcome**:
- `library.json` has 4 entries, all with `status: approved`
- `prompts/versions/` contains `orchestrator_v1.0.md`, `research_v1.0.md`, `gcp_discovery_v1.0.md`, `obsidian_writer_v1.0.md`

### Scenario 3C: CI approval flow

**Prerequisites**: At least one recommendation with `tier: recommend` in a CI report

**Steps**:
1. Identify a pending recommendation ID (e.g., `R-001`) from the CI report
2. Commit an inbox task with `apply CI recommendation R-001`
3. Wait for the run to complete

**Expected outcome**:
- The proposed change was applied (prompt file updated, or config value changed)
- Old prompt file archived to `prompts/versions/`
- `library.json` version bumped; `version_history` has a new entry with `applied_by: ci_recommendation:R-001`
- CI scores JSON for this run updated: recommendation `status: applied`
- Task record in vault confirms what was changed

---

## Sprint 4: Vault Maintenance Agent

**Goal**: Confirm auto-fix and proposal flows both work correctly.

### Scenario 4A: Auto-fix

**Setup**: Manually introduce a broken wikilink in any vault note (e.g., `[[nonexistent-note]]`).

**Steps**:
1. Trigger the Vault Maintenance Agent manually via `workflow_dispatch`
2. Check for a new git commit from the maintenance run

**Expected outcome**:
- A commit with message `vault: maintenance auto-fix [jarvis-skip]` appears
- The broken link is repaired in the commit diff
- `jarvis/vault/maintenance_{today}.md` exists and lists the auto-fix in the summary table

### Scenario 4B: Proposal report

**Setup**: Create two vault notes with substantially overlapping content.

**Steps**:
1. Trigger the Vault Maintenance Agent manually
2. Check SharePoint for the proposal report

**Expected outcome**:
- `jarvis/vault/maintenance_{today}.md` exists in SharePoint
- A `duplicate_note` proposal appears with both note paths
- The proposal includes `approval_inbox_text`
- Neither note was modified or deleted without approval

---

## Sprint 5: PR Review Agent

**Goal**: Confirm on-demand PR review lands in the vault without touching GitHub.

**Prerequisites**: `GITHUB_TOKEN` secret added (read-only, `repo:read` scope)

**Steps**:
1. Find any open GitHub PR in a repo accessible to `GITHUB_TOKEN`
2. Commit an inbox task:
   ```
   ### Task
   Title: Review PR for feature X
   priority: medium
   mode: overnight
   agents: pr_review

   ### Request
   Please review GitHub PR: https://github.com/{owner}/{repo}/pull/{number}
   ```
3. Wait for the run to complete
4. Check SharePoint for the task record

**Expected outcome**:
- `jarvis/tasks/task_{id}.md` exists in SharePoint with the PR review
- Review includes: change summary, risk assessment (HIGH/MED/LOW), specific concerns, suggested questions, approval recommendation
- Review is flagged `[HUMAN REVIEW REQUIRED]`
- No comment was posted to GitHub (verify on the PR itself)
- No 4xx/5xx errors related to GitHub in the JSON run log

---

## Cross-Sprint Validation: End-to-End Observability

After all 5 sprints are complete, run this scenario to verify the full Phase 2 stack:

**Steps**:
1. Commit a complex overnight task (e.g., GCP discovery + research + vault write)
2. Wait for the run
3. Check: JSON log, digest, validation scores, CI report (next Wednesday or Sunday), vault maintenance (next Saturday)

**Expected outcome**:
- JSON log shows all agents with confidence scores and validation results
- Digest summary includes quality scores table
- No silent failures — any issue is visible in the digest or log
- After the next CI run, the JSON logs from this run contribute to agent scores

**30-day health check**:
- At least 10 JSON log files exist in `jarvis/logs/`
- `library.json` has performance data with `sample_size ≥ 5` for all agents
- At least 2 CI reports exist in `jarvis/ci/`
- At least 1 Vault Maintenance report exists in `jarvis/vault/`
- At least 1 CI recommendation has been applied (or confirmed none met the 15% threshold)
