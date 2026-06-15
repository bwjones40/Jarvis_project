# Tasks: Jarvis Phase 2 — Agent Ecosystem Foundation

**Feature**: 002-phase2-agent-ecosystem
**Generated**: 2026-06-15
**Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md) | **Data Model**: [data-model.md](data-model.md)

---

## User Stories

| ID | Story | Priority | Phase | FR Coverage |
|----|-------|----------|-------|-------------|
| US1 | Every agent run produces a structured JSON log synced to SharePoint | P1 | 3 | FR-01–10 |
| US2 | Agent outputs are scored; failing outputs retry or skip gracefully; quality visible in digest | P1 | 4 | FR-11–19 |
| US3 | Bi-weekly stats report aggregates run data; operator sees trend visibility | P2 | 5 | FR-20–27 |

---

## Story Completion Order

```
Phase 0 Stabilization (Phase 2 below) — all blocking
    ↓
US1 (Structured Logging) → US2 (Validation Agent + Digest Quality) → US3 (Stats Report)
```

US3 can begin once US1 is complete (it reads the JSON logs US1 produces). US2 must complete before US3 for confidence scores to appear in stats data.

---

## Phase 1: Setup

*Agent version constants and settings scaffolding required before any sprint work begins.*

- [ ] T001 Add `agent_version = "1.0.0"` constant to `orchestrator/agents/orchestrator.py`
- [ ] T002 [P] Add `agent_version = "1.0.0"` constant to `orchestrator/agents/research.py`
- [ ] T003 [P] Add `agent_version = "1.0.0"` constant to `orchestrator/agents/gcp_discovery.py`
- [ ] T004 [P] Add `agent_version = "1.0.0"` constant to `orchestrator/agents/obsidian_writer.py`
- [ ] T005 Add `logging:` section to `config/settings.yaml` with keys: `log_dir: "jarvis/logs"`, `stats_dir: "jarvis/ci"`

**Phase 1 complete when**: All 4 agent files have `agent_version = "1.0.0"` and `settings.yaml` has the `logging:` block.

---

## Phase 2: Foundational (Phase 0 Stabilization)

*Eight stabilization fixes that must land before any sprint task. No sprint work may be merged until all Phase 2 items pass their validation step.*

- [ ] T006 Wire real Anthropic API call into `orchestrator/agents/research.py`: import `anthropic` and `pathlib`; load `prompts/research.md` at module level; construct `anthropic.Anthropic()` client; replace deterministic output with `client.messages.create(model="claude-haiku-4-5", ...)`; wrap in try/except with single retry on `anthropic.APIError` (10-second sleep); pass `response.usage.input_tokens` and `response.usage.output_tokens` to `token_logger.log_agent_run()`
- [ ] T007 Wire real Anthropic API call into `orchestrator/agents/obsidian_writer.py`: same pattern as T006 but uses `claude-sonnet-4-6` and loads `prompts/obsidian_writer.md`; digest and task record content now LLM-generated, not template
- [ ] T008 Add `python -m unittest discover -s tests -v` as a new step in `.github/workflows/jarvis.yml` immediately before the `Run Jarvis` step; any test failure must block the remainder of the job
- [ ] T009 Fix task ID in `orchestrator/agents/orchestrator.py` `_build_task_id()`: use `os.environ.get("GITHUB_RUN_ID")` as prefix when running in Actions; fall back to `datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")` for local runs; format: `task-{prefix}-{slug}`
- [ ] T010 Add concurrency control to `.github/workflows/jarvis.yml` `run-jarvis` job: `concurrency: group: jarvis-run` and `cancel-in-progress: false`; second triggered run queues, does not cancel
- [ ] T011 Change committed default in `config/settings.yaml` from `pii: mode: off` to `pii: mode: standard`; run full test suite after this change to confirm no regressions
- [ ] T012 Update `.github/workflows/jarvis.yml`: pin `actions/checkout` and `actions/setup-python` to latest patch versions that natively target Node.js 24; remove `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` env var from `run-jarvis` job
- [ ] T013 Update `Jarvis_Create_File_Flow` in Power Automate to check SharePoint file existence before writing: if file exists at target path, replace content (full overwrite); if new, create; document the updated flow configuration in `docs/jarvis-build-documentation.md` under Power Automate section

**Phase 2 complete when**: T006 produces non-zero token counts in dry-run output; T007 generates LLM prose in digest; T008 shows "Run unit tests" step in Actions log; T009 produces unique task IDs across runs; T010 queues concurrent runs; T011 passes full test suite; T012 eliminates Node.js 20 warning; T013 prevents duplicate vault files on re-run.

---

## Phase 3: US1 — Structured Logging

*Goal: Every agent run produces a complete, schema-valid JSON log file at `jarvis/logs/{date}/{run_id}.json` synced to SharePoint.*

**Independent test criteria**: Run Jarvis with any valid inbox task; confirm JSON log exists in SharePoint with all required fields per `contracts/run-log-schema.md`; confirm `run_id` links all agent entries; confirm `token_usage.estimated_cost_usd` is non-zero for LLM-backed agents.

- [ ] T014 [US1] Create `orchestrator/utils/run_logger.py` with `RunContext` dataclass (fields: `run_id`, `trace_id`, `log_path`) and stub for `start_run(workflow_id, trigger_source, task_id=None) -> RunContext`: generates UUID4 `run_id` and `trace_id`, creates `jarvis/logs/{YYYY-MM-DD}/{run_id}.json` with the `run` object, returns `RunContext`
- [ ] T015 [P] [US1] Implement `run_logger.log_agent_entry(run_context, entry: dict) -> None` in `orchestrator/utils/run_logger.py`: opens the JSON file, appends one `AgentLogEntry` dict to the `agents` array, re-writes the file; handles file-not-found with a warning log rather than raising
- [ ] T016 [P] [US1] Implement `run_logger.finalize_run(run_context, overall_status: str) -> None` in `orchestrator/utils/run_logger.py`: opens the JSON file, writes `completed_at` (UTC ISO 8601) and `overall_status` to the `run` object, re-writes the file
- [ ] T017 [US1] Integrate `run_logger` into `orchestrator/main.py`: call `start_run()` before the agent pipeline; detect `trigger_source` from env vars (`GITHUB_ACTIONS`, `GITHUB_EVENT_NAME`); call `log_agent_entry()` after each agent completes with timing, status, and token data; call `finalize_run()` at pipeline end with correct `overall_status`
- [ ] T018 [P] [US1] Update `orchestrator/utils/power_automate.py` `post_files()` to accept JSON log file paths alongside Markdown files in the `files[]` payload; call this from `orchestrator/main.py` after `finalize_run()` to include `jarvis/logs/{date}/{run_id}.json` in the webhook payload
- [ ] T019 [US1] Write `tests/test_run_logger.py` covering: `test_start_run_creates_valid_json` (file created with correct schema), `test_log_agent_entry_appends` (agents array grows with each call), `test_finalize_run_sets_status` (overall_status and completed_at written), `test_log_agent_entry_handles_missing_file` (graceful degradation, no exception raised)

**Phase 3 complete when**: Quickstart Sprint 1 scenario passes — JSON log exists in SharePoint after a live run; schema valid; non-zero cost for LLM agents; existing Markdown outputs unchanged.

---

## Phase 4: US2 — Validation Agent + Quality Gates

*Goal: Every `research` and `obsidian_writer` output is scored before being committed to TaskResult; retry/skip/escalate logic is live; validation scores appear in digest and run log.*

**Independent test criteria**: Set `JARVIS_VALIDATION_OVERRIDE_SCORE=0.45` and run `--dry-run`; confirm agent skipped, `TaskResult.status="partial"`, digest flags `[HUMAN REVIEW REQUIRED]`, log records `escalation_flag: true`. Set override to 0.82 and confirm one retry then acceptance. Simulate Validation Agent crash; confirm synthetic pass and pipeline completion.

- [ ] T020 [US2] Create `prompts/validation.md` with system prompt instructing the Validation Agent to score provided agent output across four dimensions (relevance, completeness, actionability, format_adherence), each 0.0–1.0, and return a structured JSON `ValidationResult` matching `contracts/validation-result-schema.md`; include instruction that `notes` field must not exceed 300 characters
- [ ] T021 [US2] Create `orchestrator/agents/validation.py` with `score_output(agent_name, output_dict, task_context, run_id) -> ValidationResult` stub: check `JARVIS_VALIDATION_OVERRIDE_SCORE` env var first and return synthetic result at that score if set; otherwise call `client.messages.create(model="claude-haiku-4-5", ...)` with `prompts/validation.md` system prompt
- [ ] T022 [US2] Implement composite score formula in `orchestrator/agents/validation.py`: `confidence_score = (relevance × 0.35) + (completeness × 0.30) + (actionability × 0.25) + (format_adherence × 0.10)`; set `pass`, `retry_recommended`, `escalate` booleans per threshold logic in `contracts/validation-result-schema.md`
- [ ] T023 [US2] Implement crash handling in `orchestrator/agents/validation.py`: wrap entire API call in try/except; on any exception return synthetic `ValidationResult` with `confidence_score: 0.90`, all dimensions 0.90, `notes: "SYNTHETIC: Validation Agent error"`; log the exception details separately without re-raising
- [ ] T024 [US2] Integrate Validation Agent into `orchestrator/main.py`: after `research` completes, call `validation.score_output("research", ...)`; after `obsidian_writer` completes, call `validation.score_output("obsidian_writer", ...)`; read all thresholds from `settings.yaml` `validation:` section
- [ ] T025 [US2] Implement three-tier recovery logic in `orchestrator/main.py`: `score ≥ pass_threshold (0.90)` → accept; `retry_min_threshold (0.60) ≤ score < pass_threshold` → retry agent once, re-score, accept if retry score `≥ retry_accept_threshold (0.80)`, else skip; `score < skip_threshold (0.60)` → skip immediately; set `escalation_flag=True` on any skip
- [ ] T026 [US2] Update `orchestrator/main.py` to set `TaskResult.status = "partial"` when any agent is skipped due to validation failure; add skipped agent name and reason to digest escalation list with `[HUMAN REVIEW REQUIRED]` prefix
- [ ] T027 [US2] Update `run_logger.log_agent_entry()` call in `orchestrator/main.py` to include `confidence_score`, `validation_pass`, `retry_count`, `skip_reason`, `escalation_flag`, `human_review_required` from the `ValidationResult` and recovery decision
- [ ] T028 [US2] Add `validation:` section to `config/settings.yaml` with: `pass_threshold: 0.90`, `retry_min_threshold: 0.60`, `retry_accept_threshold: 0.80`, `skip_threshold: 0.60`, `timeout_seconds: 30`
- [ ] T029 [US2] Update `orchestrator/agents/obsidian_writer.py` to include a "Run Quality Summary" section in the morning digest: Markdown table with one row per agent showing agent name, confidence score (or "N/A" for non-validated agents), PASS/FAIL status, retry count, escalation flag
- [ ] T030 [US2] Write `tests/test_validation.py` covering: `test_composite_score_formula` (verify weighted average), `test_threshold_tiers` (verify pass/retry/escalate boolean assignment for each tier), `test_synthetic_pass_on_crash` (exception → confidence_score 0.90), `test_override_score_env_var` (JARVIS_VALIDATION_OVERRIDE_SCORE respected), `test_validation_not_called_for_gcp_discovery` (scope constraint enforced in main.py)

**Phase 4 complete when**: Quickstart Sprint 2 scenarios A, B, and C all pass.

---

## Phase 5: US3 — Bi-Weekly Stats Report

*Goal: Separate GitHub Actions job runs Sunday and Tuesday nights, reads JSON run logs, produces aggregated stats report in SharePoint.*

**Independent test criteria**: Run stats reporter against 3+ synthetic JSON log files; confirm `jarvis/ci/stats_{date}.md` and `jarvis/ci/stats_{date}.json` produced with correct per-agent rows; confirm second run uses first run's `analysis_window_end` as its window start; confirm malformed log file is skipped without crashing.

- [ ] T031 [US3] Create `orchestrator/agents/stats_reporter.py` with `run_stats_report(log_dir, stats_dir, webhook_url=None) -> None` stub and helper stubs: `_find_window_start(stats_dir) -> str | None` and `_aggregate_agent_stats(entries: list) -> list`
- [ ] T032 [P] [US3] Implement `_find_window_start(stats_dir)` in `orchestrator/agents/stats_reporter.py`: glob `jarvis/ci/stats_*.json`, sort descending by filename date, open most recent, read `analysis_window_end` field; return `None` if no files found (first run)
- [ ] T033 [P] [US3] Implement log scanning in `orchestrator/agents/stats_reporter.py`: iterate all `jarvis/logs/{date}/*.json` files; filter to entries where `run.started_at > window_start` (or all files if `window_start` is None); parse `agents` arrays into a flat list of `AgentLogEntry` dicts; skip malformed files with `warnings.warn()` — no exception raised
- [ ] T034 [US3] Implement `_aggregate_agent_stats(entries)` in `orchestrator/agents/stats_reporter.py`: group by `agent_name`; compute per-agent: `run_count`, `success_rate` (status=success / total), `avg_confidence_score` (mean of non-null confidence_score; omit for non-validated agents), `avg_latency_ms`, `avg_tokens_per_run`, `total_cost_usd` (sum of estimated_cost_usd), `retry_count` (sum of retry_count), `escalation_count` (count of escalation_flag=true entries)
- [ ] T035 [US3] Implement `run_stats_report()` in `orchestrator/agents/stats_reporter.py`: call `_find_window_start()`, scan logs, call `_aggregate_agent_stats()`, write `jarvis/ci/stats_{YYYY-MM-DD}.md` (Markdown table per `contracts/stats-report-schema.md`) and `jarvis/ci/stats_{YYYY-MM-DD}.json`; if `webhook_url` provided, call `power_automate.post_files()` with both output files
- [ ] T036 [US3] Add `--mode stats_report` handler to `orchestrator/main.py` argument parser: when mode is `stats_report`, read `log_dir` and `stats_dir` from `settings.yaml`, call `stats_reporter.run_stats_report()`, and exit without running the task pipeline
- [ ] T037 [US3] Add `run-stats-report` job to `.github/workflows/jarvis.yml` with schedule `cron: "0 23 * * 0,2"` (Sunday and Tuesday 11PM UTC); include: checkout, setup-python (Python 3.12), install dependencies, run unit tests, run stats report via `python orchestrator/main.py --mode stats_report`; add `concurrency: group: jarvis-stats, cancel-in-progress: false`
- [ ] T038 [US3] Write `tests/test_stats_reporter.py` covering: `test_first_run_scans_all_logs` (None window_start → all files included), `test_window_start_from_prior_report` (analysis_window_end read correctly from prior JSON), `test_malformed_log_skipped` (bad JSON does not raise, emits warning), `test_aggregate_stats_accuracy` (known fixture data produces correct metric values), `test_confidence_score_absent_for_unvalidated_agents` (gcp_discovery and orchestrator have no avg_confidence_score field)

**Phase 5 complete when**: Quickstart Sprint 3 scenarios B and C pass — stats report appears in SharePoint after manual trigger; subsequent run uses correct analysis window.

---

## Phase 6: Polish & Cross-Cutting

- [ ] T039 Keep `prompt_id` and `prompt_version` out of `AgentLogEntry` in `orchestrator/utils/run_logger.py` and `contracts/run-log-schema.md` — Prompt Library remains deferred, so those fields should stay absent from the live schema
- [ ] T040 [P] Move outdated contract files to `specs/002-phase2-agent-ecosystem/contracts/archive/`: `prompt-library-schema.md`, `ci-report-schema.md`, `maintenance-report-schema.md`; update any references in `plan.md` or `tasks.md` to the archived location
- [ ] T041 Remove the Power Automate smoke-test step from `.github/workflows/jarvis.yml` so production runs no longer write `jarvis/test.md`

**Phase 6 complete when**: No `prompt_id`/`prompt_version` in live log files; no obsolete contracts in the active contracts directory; no `jarvis/test.md` appearing in SharePoint on normal production runs.

---

## Dependencies Summary

```
T001–T005  (Phase 1: Setup)
    ↓
T006–T013  (Phase 2: Phase 0 Stabilization)
    ↓
T014–T019  (Phase 3: US1 Structured Logging)
    ↓
T020–T030  (Phase 4: US2 Validation Agent)
    ↓
T031–T038  (Phase 5: US3 Stats Report)
    ↓
T039–T041  (Phase 6: Polish)
```

### Parallel Opportunities Within Phases

**Phase 1** (T001–T005): T001–T004 are fully parallel (different agent files). T005 is independent.

**Phase 2** (T006–T013): T008 (CI tests), T010 (concurrency), T011 (PII mode), T012 (Node.js) are all parallel with each other and with T006/T007. T006 and T007 should be sequential (research first, validate, then obsidian_writer). T013 (Power Automate) is fully parallel with all Python changes.

**Phase 3** (T014–T019): T014, T015, T016 are parallel (separate functions in the same file — implement stubs first). T017 depends on T014–T016. T018 is parallel with T017. T019 (tests) can be written in parallel with T014–T016.

**Phase 4** (T020–T030): T020 (prompt) and T021 (stub) are parallel. T022 and T023 depend on T021. T024 depends on T020–T023. T025–T027 depend on T024. T028 is parallel with T024. T029 (digest update) depends on T025–T027. T030 (tests) can be written in parallel with T021–T028.

**Phase 5** (T031–T038): T031 (stubs) first. T032 and T033 are parallel (independent functions). T034 depends on T033. T035 depends on T032–T034. T036 depends on T035. T037 is parallel with T035–T036. T038 (tests) can be written in parallel with T032–T036.

---

## Implementation Strategy

**MVP scope (Phase 2 + Phase 3 only)**: Complete T006 (LLM wiring for research) + T014–T018 (structured logging). This gives real token data in logs with no change to existing agent behavior. Every subsequent phase adds value incrementally.

**Sprint boundaries**:
- Phase 0 + Phase 1 + Phase 2 complete → system is stable, LLM-backed, with regression coverage
- Phase 3 complete → JSON logs in SharePoint after every run
- Phase 4 complete → quality gates live; digest shows validation scores
- Phase 5 complete → trend data available bi-weekly
- Phase 6 complete → no dead code, no noise in SharePoint

**Zero-regression rule**: Phases 3–5 must not change the behavior of Phase 1 agents for valid inputs. Use `python orchestrator/main.py --dry-run` to test new code paths before enabling in production runs. The CI unit test step (T008) catches regressions automatically on every push.

---

## Total Task Count

| Phase | Tasks | Story |
|-------|-------|-------|
| Phase 1: Setup | 5 (T001–T005) | — |
| Phase 2: Foundational (Phase 0) | 8 (T006–T013) | — |
| Phase 3: US1 Logging | 6 (T014–T019) | US1 |
| Phase 4: US2 Validation | 11 (T020–T030) | US2 |
| Phase 5: US3 Stats Report | 8 (T031–T038) | US3 |
| Phase 6: Polish | 3 (T039–T041) | — |
| **Total** | **41** | |
