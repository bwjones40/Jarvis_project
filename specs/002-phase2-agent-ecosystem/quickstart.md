# Quickstart: Jarvis Phase 2 Validation Guide

**Feature**: 002-phase2-agent-ecosystem
**Revised**: 2026-06-15

Validate each phase and sprint in order. Each section is self-contained — complete Phase 0 before Sprint 1, Sprint 1 before Sprint 2, etc.

---

## Prerequisites

All Phase 1 validation scenarios in `specs/001-jarvis-mvp/quickstart.md` must pass before beginning Phase 2 validation.

Required secrets in GitHub Actions:
- `ANTHROPIC_API_KEY` (existing — now used for real API calls)
- `POWER_AUTOMATE_WEBHOOK_URL` (existing)

---

## Phase 0: Stabilization

### P0-1 + P0-2: Real LLM calls wired

> **Status**: Pending — T006 and T007 not yet implemented. `research.py` and `obsidian_writer.py` still produce zero-token synthetic output. Running the steps below before these tasks land will show `input_tokens: 0`.

**Steps**:
1. Run `python orchestrator/main.py --dry-run` with a valid task in `jarvis/inbox.md`
2. Check terminal output for token usage

**Expected outcome**:
- `token_usage.input_tokens > 0` and `output_tokens > 0` for `research` and `obsidian_writer`
- Digest content is LLM-generated prose, not a template placeholder
- No `ANTHROPIC_API_KEY` errors

**Failure indicator**: Token counts are 0 → LLM wiring not complete

---

### P0-3: Unit tests run in CI

**Steps**:
1. Push any change to the repo
2. Check the GitHub Actions run log

**Expected outcome**:
- A "Run unit tests" step appears before "Run Jarvis"
- All 50+ tests pass (`Ran N tests in Xs ... OK`)

**Failure indicator**: Step absent → `jarvis.yml` not updated; tests fail → regression introduced

---

### P0-4: Unique task IDs

**Steps**:
1. Trigger two manual `workflow_dispatch` runs back-to-back with the same inbox task
2. Check SharePoint for task records

**Expected outcome**:
- Two distinct task files exist (different run IDs in filenames)
- Neither overwrote the other

---

### P0-5: Workflow concurrency (queue behavior)

**Steps**:
1. Trigger two `workflow_dispatch` runs almost simultaneously
2. Check Actions tab

**Expected outcome**:
- First run shows "In progress"
- Second run shows "Queued" (not "Cancelled")
- Both runs complete successfully

---

### P0-6: PII mode default

**Steps**:
1. Run `python -m unittest discover -s tests -v` locally
2. Check `config/settings.yaml` for `pii.mode`

**Expected outcome**:
- All tests pass with `pii.mode: standard`
- No `[REDACTED_*]` markers in dry-run output for non-sensitive task content

---

### P0-7: Node.js 24 — no deprecation warning

**Steps**:
1. Push any change and check the Actions run log

**Expected outcome**:
- No "Node.js 20 is deprecated" warning in the log
- `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` line is absent from `jarvis.yml`

---

### P0-8: Power Automate upsert

**Steps**:
1. Run Jarvis twice with the same task title (same inbox content, two sequential runs)
2. Check SharePoint for the task record file

**Expected outcome**:
- Only one file exists at the expected vault path (not two versioned copies)
- File content reflects the second run's output

---

## Sprint 1: Structured Logging

**Goal**: Confirm every agent run produces a JSON log file in SharePoint.

**Steps**:
1. Commit a valid task to `jarvis/inbox.md`
2. Wait for the Actions run to complete
3. Check SharePoint under `Jarvis/logs/{today}/`

**Expected outcome**:
- A file `{run_id}.json` exists in SharePoint
- File contains a `run` object with `run_id`, `trace_id`, `workflow_id`, `overall_status`
- File contains an `agents` array with one entry per agent that executed
- Each entry has `timestamp`, `agent_name`, `agent_version`, `status`, `latency_ms`, `token_usage`
- `token_usage.estimated_cost_usd` is non-zero for all LLM-backed agents
- `overall_status` matches the task outcome

**Validation command** (run in PowerShell from the repo root after the Actions run completes):

```powershell
# Update VAULT_ROOT if your OneDrive path differs
$VAULT_ROOT = "C:\Users\jonesbrade\OneDrive - Tyson Online\Meetings\Files\Analytics\Braden\Obsidian\AIOps_Vault"

python - $VAULT_ROOT <<'PY'
import json, sys
from pathlib import Path
from datetime import date

vault_root = Path(sys.argv[1])
log_dir = vault_root / "jarvis" / "logs" / date.today().isoformat()
files = list(log_dir.glob("*.json"))
if not files:
    print(f"FAIL: No log files found in {log_dir}")
    sys.exit(1)

errors = []
for f in files:
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"{f.name}: could not parse — {e}")
        continue
    if "run" not in data:
        errors.append(f"{f.name}: missing 'run' object")
    if "agents" not in data or len(data["agents"]) == 0:
        errors.append(f"{f.name}: missing or empty 'agents' array")
        continue
    for entry in data["agents"]:
        name = entry.get("agent_name", "unknown")
        for field in ("run_id", "agent_name", "status"):
            if field not in entry:
                errors.append(f"{f.name} [{name}]: missing field '{field}'")
        token = entry.get("token_usage", {})
        if token.get("total", -1) < 0:
            errors.append(f"{f.name} [{name}]: token_usage.total is negative")
        if name in ("research", "obsidian_writer"):
            cost = token.get("estimated_cost_usd", 0)
            if cost <= 0:
                errors.append(f"{f.name} [{name}]: estimated_cost_usd is {cost} — LLM not called")

if errors:
    print("FAIL:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print(f"PASS: {len(files)} log file(s) found and valid")
PY
```

**Failure indicators**:
- No JSON file in SharePoint → `power_automate.py` not updated to include log files
- JSON file local but not in SharePoint → webhook payload not including log
- `estimated_cost_usd` is 0.0 → Phase 0 LLM wiring not complete

**Regression check**: Existing Markdown vault outputs (task record, digest) must still appear in SharePoint unchanged.

---

## Sprint 2: Validation Agent

**Goal**: Agent outputs are scored; retry/skip logic fires; results visible in digest and JSON log.

### Scenario 2A: High-confidence pass

**Steps**:
1. Commit a clear, well-formed task (specific research question with clear deliverable)
2. Wait for the run to complete
3. Check JSON log and morning digest

**Expected outcome**:
- JSON log: `research` and `obsidian_writer` entries have `confidence_score ≥ 0.90`, `validation_pass: true`, `retry_count: 0`
- Digest: "Run Quality Summary" table present, all agents show PASS
- `overall_status: completed`

---

### Scenario 2B: Forced retry and skip

Run locally without `--dry-run`. Since `POWER_AUTOMATE_WEBHOOK_URL` is not set locally, nothing posts to SharePoint. Check `jarvis/logs/{today}/{run_id}.json` after each run.

**Sub-scenario 2B-low — immediate skip (score below skip_threshold)**

```powershell
$env:JARVIS_VALIDATION_OVERRIDE_SCORE = "0.45"
python orchestrator/main.py
Remove-Item Env:\JARVIS_VALIDATION_OVERRIDE_SCORE
```

**Expected outcome** in the JSON log for `research` and `obsidian_writer` entries:
- `confidence_score: 0.45`
- `escalation_flag: true`
- `validation_pass: false`
- `retry_count: 0` — score is below `skip_threshold` (0.60), so no retry is attempted
- `skip_reason: "validation_score_below_skip_threshold"`
- `clarifications_needed` contains `[HUMAN REVIEW REQUIRED]` entries

In `run.overall_status`: `partial` (also visible as `status: "partial"` in stdout task_result)

**Sub-scenario 2B-mid — retry zone (score triggers retry, retry accepted)**

```powershell
$env:JARVIS_VALIDATION_OVERRIDE_SCORE = "0.82"
python orchestrator/main.py
Remove-Item Env:\JARVIS_VALIDATION_OVERRIDE_SCORE
```

**Expected outcome** in the JSON log:
- `retry_count: 1` — score (0.82) is in range `[retry_min_threshold, pass_threshold)` so one retry fires
- `confidence_score: 0.82`
- `validation_pass: true` — retry score meets `retry_accept_threshold` (0.80)
- `escalation_flag: false`
- `run.overall_status: completed`

---

### Scenario 2C: Validation Agent crash

Setting `ANTHROPIC_API_KEY` to an invalid value does **not** isolate the crash to the Validation Agent — it also breaks `research.py`, which would crash the pipeline before validation runs. Test this scenario via the unit test that covers it directly:

```powershell
python -m unittest tests.test_validation.ValidationAgentTests.test_synthetic_pass_on_crash -v
```

**Expected outcome**: `test_synthetic_pass_on_crash ... ok`

This test patches the Anthropic client to raise an exception inside `score_output` and confirms that `confidence_score` falls back to `0.90` with `notes` containing `"SYNTHETIC"` — matching the intended crash-recovery behavior.

**Regression check**: Digest still produced; task record still written; no exception propagated to main process.

---

## Sprint 3: Monitoring

### Scenario 3A: Digest quality summary

**Steps**:
1. Complete a successful overnight run (Sprint 2 must be live)
2. Open the morning digest in SharePoint/Obsidian

**Expected outcome**:
- "Run Quality Summary" section present
- Table shows one row per agent with: agent name, confidence score (or N/A), PASS/FAIL, retry count, escalation flag

---

### Scenario 3B: Stats report — first run

**Steps**:
1. Ensure at least 2 completed JSON log files exist in `jarvis/logs/`
2. Trigger the stats report manually via `workflow_dispatch` selecting the `run-stats-report` job

**Expected outcome**:
- `jarvis/ci/stats_{today}.md` exists in SharePoint with per-agent rows
- `jarvis/ci/stats_{today}.json` exists with `analysis_window_start: null` (first run)
- All rows have non-zero `run_count`
- `avg_confidence_score` present only for `research` and `obsidian_writer`

---

### Scenario 3C: Stats report — subsequent run window

**Steps**:
1. Run the stats report twice (with at least one overnight run between them)
2. Check the second stats JSON

**Expected outcome**:
- `analysis_window_start` in the second report equals `analysis_window_end` from the first report
- The second report contains only runs from after the first report's window end
- No runs appear in both reports

---

## Cross-Phase Regression Check

After all sprints complete, run this to verify the full Phase 2 stack hasn't broken Phase 1 behavior:

**Steps**:
1. Commit a standard overnight task
2. Wait for run

**Expected outcome**:
- JSON log in SharePoint ✓
- Digest in SharePoint with Run Quality Summary table ✓
- Task record in SharePoint with unique ID ✓
- No duplicate files (Power Automate upsert working) ✓
- All agents show PASS in digest (normal task) ✓
- Unit tests passed in CI before run ✓
