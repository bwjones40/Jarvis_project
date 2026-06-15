# Tasks: Jarvis Phase 2 — Agent Ecosystem Expansion

**Feature**: 003-phase2-agent-ecosystem
**Generated**: 2026-06-14
**Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md) | **Data Model**: [data-model.md](data-model.md)

---

## User Stories

| ID | Story | Priority | Sprint | FR Coverage |
|----|-------|----------|--------|-------------|
| US1 | Every agent run produces a structured, queryable JSON log synced to SharePoint | P1 | 1 | FR-01–05 |
| US2 | Agent outputs are scored for quality; failing outputs retry or skip gracefully | P1 | 2 | FR-06–13 |
| US3 | CI Agent analyzes logs bi-weekly and produces human-approvable improvement recommendations | P2 | 3 | FR-14–26 |
| US4 | Vault Maintenance Agent auto-fixes low-risk issues and proposes high-risk changes weekly | P2 | 4 | FR-27–32 |
| US5 | On-demand PR reviews are triggered via inbox task and written to vault only | P3 | 5 | FR-33–36 |

---

## Story Completion Order

```
US1 (Logging) → US2 (Validation) → US3 (CI + Prompt Library)
                                  → US4 (Vault Maintenance)  [parallel with US3 after US2]
                                  → US5 (PR Review)          [parallel with US3/US4 after US2]
```

US3, US4, and US5 can begin in parallel once US2 is complete. US1 must fully complete before US2.

---

## Phase 1: Setup

*Project initialization tasks required before any user story work begins.*

- [ ] T001 Add `agent_version = "1.0.0"` constant to `orchestrator/agents/orchestrator.py`
- [ ] T002 [P] Add `agent_version = "1.0.0"` constant to `orchestrator/agents/research.py`
- [ ] T003 [P] Add `agent_version = "1.0.0"` constant to `orchestrator/agents/gcp_discovery.py`
- [ ] T004 [P] Add `agent_version = "1.0.0"` constant to `orchestrator/agents/obsidian_writer.py`
- [ ] T005 Add `logging:` section to `config/settings.yaml` with keys: `log_dir: "jarvis/logs"`, `ci_dir: "jarvis/ci"`, `vault_dir: "jarvis/vault"`
- [ ] T006 Create `prompts/versions/` directory and copy existing prompts: `orchestrator_v1.0.md`, `research_v1.0.md`, `gcp_discovery_v1.0.md`, `obsidian_writer_v1.0.md`
- [ ] T007 Create `prompts/library.json` initialized with 4 entries (orchestrator, research, gcp_discovery, obsidian_writer) per schema in `contracts/prompt-library-schema.md`; all `status: "approved"`, `sample_size: 0`, `last_evaluated: today`

**Phase 1 complete when**: All 4 agents have `agent_version`, settings.yaml has `logging:` block, `prompts/library.json` exists with 4 valid entries, `prompts/versions/` contains 4 archived prompt files.

---

## Phase 2: Foundational

*Shared infrastructure that blocks all user stories.*

- [ ] T008 Create `orchestrator/utils/run_logger.py` with function stubs: `start_run()`, `log_agent_entry()`, `finalize_run()` — return types matching `RunLog` and `AgentLogEntry` from `data-model.md`
- [ ] T009 Generate UUID4 `run_id` and `trace_id` in `orchestrator/main.py` at the top of the main execution block; pass both to all downstream agent calls
- [ ] T010 Update `orchestrator/utils/power_automate.py` `post_files()` to accept and include JSON log files alongside Markdown files in the webhook payload `files[]` array
- [ ] T011 Update `orchestrator/utils/inbox_parser.py` to recognize three new task types: `ci_approval` (title matches `apply CI recommendation R-\d+`), `vault_approval` (title matches `apply vault maintenance proposal M-\d+`), `pr_review` (agents field contains `pr_review`); add parsed fields for each type

**Phase 2 complete when**: `run_id` and `trace_id` are generated on every run, `power_automate.py` can include JSON files in payload, inbox parser recognizes all three new task types without breaking existing task parsing.

---

## Phase 3: US1 — Structured Logging

*Goal: Every agent run produces a complete, schema-valid JSON log file at `jarvis/logs/{date}/{run_id}.json` that is synced to SharePoint.*

**Independent test criteria**: Run Jarvis with any valid inbox task; confirm JSON log exists in SharePoint with all required fields per `contracts/run-log-schema.md`. Verify `run_id` links all agent entries. Verify `token_usage.estimated_cost_usd` is populated.

- [ ] T012 [US1] Implement `run_logger.start_run(workflow_id, trigger_source, task_id=None)` in `orchestrator/utils/run_logger.py`: generates UUID4 `run_id` and `trace_id`, creates `jarvis/logs/{YYYY-MM-DD}/{run_id}.json` with `run` object, returns `RunContext` dataclass
- [ ] T013 [US1] Implement `run_logger.log_agent_entry(run_context, entry_dict)` in `orchestrator/utils/run_logger.py`: appends one `AgentLogEntry` dict to the `agents` array in the JSON file; handles file-not-found gracefully
- [ ] T014 [US1] Implement `run_logger.finalize_run(run_context, overall_status)` in `orchestrator/utils/run_logger.py`: writes `completed_at` timestamp and `overall_status` to the `run` object in the JSON file
- [ ] T015 [US1] Integrate `run_logger` into `orchestrator/main.py`: call `start_run()` before the agent pipeline; call `log_agent_entry()` after each agent completes (orchestrator, research, gcp_discovery, obsidian_writer); call `finalize_run()` at the end with the correct `overall_status`
- [ ] T016 [US1] Update `orchestrator/utils/token_logger.py` `log_agent_run()` to share `input`, `output`, `total`, and `estimated_cost_usd` fields with the `AgentLogEntry` written by `run_logger` (pass token data to `log_agent_entry` call in `main.py`)
- [ ] T017 [US1] Update `orchestrator/utils/power_automate.py` `post_files()` call in `main.py` to include `jarvis/logs/{date}/{run_id}.json` in the `files[]` array alongside existing Markdown vault files
- [ ] T018 [US1] Add `trigger_source` detection to `orchestrator/main.py`: set to `github_actions_cron` if `GITHUB_ACTIONS=true` and no `GITHUB_EVENT_NAME`, `inbox_push` if event is `push`, `workflow_dispatch` if event is `workflow_dispatch`

**Phase 3 complete when**: Quickstart Sprint 1 validation passes — JSON log exists in SharePoint after a live run, all required schema fields are present, `run_id` matches across all agent entries.

---

## Phase 4: US2 — Validation Agent + Quality Gates

*Goal: Every subagent output is scored; scores drive retry/skip/escalate decisions logged in the run JSON and surfaced in the morning digest.*

**Independent test criteria**: Force a synthetic low-confidence output (score < 0.60); confirm the agent is skipped, `TaskResult.status = "partial"`, digest includes `[HUMAN REVIEW REQUIRED]`, and the run log records `escalation_flag: true`. Force a mid-range score (0.60–0.89); confirm one retry occurs before acceptance or skip.

- [ ] T019 [US2] Create `prompts/validation.md` with system prompt instructing the Validation Agent to score agent outputs across four dimensions (relevance, completeness, compliance, format_adherence) and return a structured JSON ValidationResult; include PII-detection instruction for `compliance` dimension
- [ ] T020 [US2] Create `orchestrator/agents/validation.py` with `score_output(agent_name, output_dict, task_context, run_id)` function stub that calls the Anthropic API using `claude-haiku-4-5` with the prompt from `prompts/validation.md`
- [ ] T021 [US2] Implement composite score calculation in `orchestrator/agents/validation.py`: `confidence_score = (relevance × 0.35) + (completeness × 0.30) + (compliance × 0.25) + (format_adherence × 0.10)`; set `pass`, `retry_recommended`, `escalate` booleans per threshold logic in `contracts/validation-result-schema.md`
- [ ] T022 [US2] Implement crash handling in `orchestrator/agents/validation.py`: wrap the API call in try/except; on any exception, return a synthetic `ValidationResult` with `confidence_score: 0.90`, `pass: true`, `notes: "SYNTHETIC: Validation Agent error"`, and log the exception as a separate `AgentLogEntry` with `status: "failed"` for the validation agent itself
- [ ] T023 [US2] Integrate Validation Agent into `orchestrator/main.py`: after each subagent (research, gcp_discovery, obsidian_writer) call `validation.score_output()`; store `ValidationResult` to drive recovery decision
- [ ] T024 [US2] Implement three-tier recovery logic in `orchestrator/main.py`: if `confidence_score ≥ 0.90` accept; if `0.60 ≤ confidence_score < 0.90` retry agent once then re-score; if score still `< 0.60` or initial score `< 0.60` skip agent and set `escalation_flag=True`
- [ ] T025 [US2] Update `orchestrator/main.py` to set `TaskResult.status = "partial"` when any agent is skipped due to validation failure; add skipped agent name and reason to the `clarifications_needed` list with `[HUMAN REVIEW REQUIRED]` prefix
- [ ] T026 [US2] Update `run_logger.log_agent_entry()` call in `orchestrator/main.py` to include `confidence_score`, `validation_pass`, `retry_count`, `escalation_flag`, `human_review_required`, `skip_reason` from the `ValidationResult` and recovery decision
- [ ] T027 [US2] Update `orchestrator/agents/obsidian_writer.py` to include a validation scores table in the task record Markdown: one row per agent with agent name, confidence score, pass/fail, retry count

**Phase 4 complete when**: Quickstart Sprint 2 scenarios A, B, and C pass — including forced skip-degrade, retry window, and Validation Agent crash handling without pipeline halt.

---

## Phase 5: US3 — CI Agent + Prompt Library

*Goal: Bi-weekly CI analysis produces scored, evidence-backed recommendations in vault; operator can approve via inbox task; changes are applied, archived, and tracked in `prompts/library.json`.*

**Independent test criteria**: Run CI Agent against 5 synthetic JSON log files (covering 3+ runs); confirm a Markdown report and JSON scores file appear in vault; confirm at least one recommendation with `tier: recommend` is present if synthetic logs contain degraded performance data. Approve a recommendation via inbox task; confirm the prompt file is updated and archived.

- [ ] T028 [US3] Create `prompts/ci_agent.md` with system prompt instructing the CI Agent to analyze agent log data, compute weighted dimension scores, identify improvement opportunities, and output structured recommendations in the format defined in `contracts/ci-report-schema.md`
- [ ] T029 [P] [US3] Create `orchestrator/agents/ci_agent.py` with function stubs: `analyze_logs(log_dir, since_date)`, `score_agents(entries)`, `generate_recommendations(scores, library)`, `write_report(ci_run, report_path, scores_path)`, `update_library_performance(library_path, agent_scores)`
- [ ] T030 [US3] Implement `ci_agent.analyze_logs(log_dir, since_date)` in `orchestrator/agents/ci_agent.py`: iterate all `jarvis/logs/{date}/*.json` files within the analysis window; parse `AgentLogEntry` records; skip malformed files with a warning log; return flat list of entries
- [ ] T031 [US3] Implement `ci_agent.score_agents(entries)` in `orchestrator/agents/ci_agent.py`: group entries by `agent_name`; compute 7-dimension composite score per agent using weights from `contracts/ci-report-schema.md`; include `low_sample_warning: true` if total run count < 5; apply adjusted 20% threshold when `low_sample_warning` is true
- [ ] T032 [US3] Implement `ci_agent.generate_recommendations(scores, library)` in `orchestrator/agents/ci_agent.py`: call Anthropic API with `claude-sonnet-4-6`; pass agent scores and prompt library metadata; filter output to keep only recommendations with `ci_score_delta ≥ 0.15` (or 0.20 if low sample); assign sequential IDs (`R-001`, `R-002`, …); set `risk_level: HIGH` automatically for any recommendation touching PII guard or auto-send logic
- [ ] T033 [US3] Implement `ci_agent.write_report(ci_run, report_path, scores_path)` in `orchestrator/agents/ci_agent.py`: write `jarvis/ci/ci_report_{date}.md` in the format defined in `contracts/ci-report-schema.md`; write `jarvis/ci/ci_scores_{date}.json`; include both files in the Power Automate webhook payload
- [ ] T034 [US3] Implement `ci_agent.update_library_performance(library_path, agent_scores)` in `orchestrator/agents/ci_agent.py`: update `performance` fields (avg_confidence_score, validation_pass_rate, avg_latency_ms, avg_tokens_per_run, sample_size, last_evaluated) for each agent entry in `prompts/library.json` based on current cycle data
- [ ] T035 [US3] Add CI Agent cron job to `.github/workflows/jarvis.yml`: new job `run-ci-agent` with schedule `cron: "0 23 * * 0,3"`; same checkout/python/install steps as `run-jarvis`; run `python orchestrator/main.py --mode ci`; add `--mode` flag handler to `orchestrator/main.py`
- [ ] T036 [US3] Implement CI approval task handler in `orchestrator/main.py`: detect inbox task type `ci_approval` (title matches `apply CI recommendation R-{id}`); load latest `jarvis/ci/ci_scores_*.json` (most recent file); find recommendation by ID; dispatch to `apply_ci_recommendation(recommendation, library_path)`
- [ ] T037 [US3] Implement `apply_ci_recommendation(recommendation, library_path)` function in `orchestrator/main.py`: for `type: prompt_improvement` — copy current prompt to `prompts/versions/{agent}_v{version}.md`, write new prompt content, bump version in `library.json`, reset `performance.sample_size` to 0; for `type: config_change` — update `config/settings.yaml` at the specified key; update recommendation `status: applied` in scores JSON; write task record confirming what was applied

**Phase 5 complete when**: Quickstart Sprint 3 scenarios A, B, and C pass — CI report appears in vault, library.json has performance data, inbox approval applies a prompt change and archives the old version.

---

## Phase 6: US4 — Vault Maintenance Agent

*Goal: Weekly automated vault cleanup; low-risk issues auto-fixed and committed; high-risk proposals land in vault for operator review and inbox approval.*

**Independent test criteria**: Introduce a broken wikilink and a naming violation; trigger Vault Maintenance; confirm auto-fix commit appears with message `vault: maintenance auto-fix [jarvis-skip]` and both issues are fixed. Create two overlapping vault notes; confirm a `duplicate_note` proposal appears in the maintenance report without either note being modified.

- [ ] T038 [US4] Create `prompts/vault_maintenance.md` with system prompt instructing the Vault Maintenance Agent to classify vault issues by risk level, generate concise proposal descriptions, and output structured JSON matching the internal schema in `contracts/maintenance-report-schema.md`
- [ ] T039 [P] [US4] Create `orchestrator/agents/vault_maintenance.py` with function stubs: `scan_vault(vault_root)`, `apply_auto_fixes(fixes)`, `generate_proposals(high_risk_issues)`, `write_report(run, report_path)`, `commit_auto_fixes(fixes)`
- [ ] T040 [US4] Implement `vault_maintenance.scan_vault(vault_root)` in `orchestrator/agents/vault_maintenance.py`: walk all `.md` files under `vault_root`; detect broken wikilinks (regex `\[\[([^\]]+)\]\]` with path check), naming violations (uppercase or space in filename), missing frontmatter (`created`/`last_updated` absent), empty files (0 content lines), and duplicate notes (content similarity via word overlap ratio > 0.85); return categorized issue list
- [ ] T041 [US4] Implement `vault_maintenance.apply_auto_fixes(fixes)` in `orchestrator/agents/vault_maintenance.py`: for each fix type — repair broken links (update link target to correct path), rename files (kebab-case), add missing frontmatter (derive timestamps from file metadata), delete empty files (verify 0 inbound links first); wrap all writes in a try/except that aborts ALL changes on any error and returns the fix list as proposals instead
- [ ] T042 [US4] Implement `vault_maintenance.commit_auto_fixes(applied_fixes)` in `orchestrator/agents/vault_maintenance.py`: stage changed/renamed/deleted files via `subprocess` git commands; commit with message `vault: maintenance auto-fix [jarvis-skip]`; capture and return commit SHA
- [ ] T043 [US4] Implement `vault_maintenance.generate_proposals(high_risk_issues)` in `orchestrator/agents/vault_maintenance.py`: call Anthropic API with `claude-haiku-4-5`; pass issue details; generate human-readable description and proposed action for each issue; assign sequential proposal IDs (`M-001`, `M-002`, …); set `approval_inbox_text` for each
- [ ] T044 [US4] Implement `vault_maintenance.write_report(run, report_path)` in `orchestrator/agents/vault_maintenance.py`: write `jarvis/vault/maintenance_{date}.md` in format defined in `contracts/maintenance-report-schema.md`; include auto-fix summary table and all proposals with approval instructions; include report file in Power Automate webhook payload
- [ ] T045 [US4] Add Vault Maintenance Agent cron job to `.github/workflows/jarvis.yml`: new job `run-vault-maintenance` with schedule `cron: "0 22 * * 6"`; run `python orchestrator/main.py --mode vault_maintenance`; add `vault_maintenance` to `--mode` handler in `orchestrator/main.py`
- [ ] T046 [US4] Implement vault approval task handler in `orchestrator/main.py`: detect task type `vault_approval` (title matches `apply vault maintenance proposal M-{id}`); load most recent `jarvis/vault/maintenance_*.md` and its corresponding internal JSON; find proposal by ID; apply the specific action (merge notes, archive stale record, move to correct folder); write task record confirming action taken

**Phase 6 complete when**: Quickstart Sprint 4 scenarios A and B pass — auto-fix commit appears for injected broken link/naming violation; duplicate note proposal appears in report without either note being touched.

---

## Phase 7: US5 — PR Review Agent

*Goal: Operator submits an inbox task with a GitHub PR URL; a structured review lands in the vault within one run; no write operations occur on GitHub.*

**Independent test criteria**: Submit inbox task with a real PR URL; confirm `jarvis/tasks/{task_id}.md` appears in vault with all review sections (summary, risk, concerns, questions, recommendation) and `[HUMAN REVIEW REQUIRED]` flag; confirm no PR comment was posted to GitHub; confirm JSON log shows no `POST`/`PATCH`/`DELETE` GitHub API calls.

- [ ] T047 [US5] Create `prompts/pr_review.md` with system prompt instructing the PR Review Agent to analyze a pull request diff and produce a structured review with: change summary, risk assessment (HIGH/MED/LOW), specific concerns by category (security, logic, performance), suggested questions for the PR author, and an approval recommendation; include instruction to never produce GitHub comment text as output
- [ ] T048 [P] [US5] Create `orchestrator/agents/pr_review.py` with function stubs: `fetch_pr(repo, pr_number, github_token)`, `analyze_pr(pr_data, vault_context, task_context)`
- [ ] T049 [US5] Implement `pr_review.fetch_pr(repo, pr_number, github_token)` in `orchestrator/agents/pr_review.py`: make two read-only `requests.get` calls — `GET /repos/{repo}/pulls/{pr_number}` and `GET /repos/{repo}/pulls/{pr_number}/files`; raise `ValueError` if `GITHUB_TOKEN` is absent or if response is not 200; truncate diff to 2000 changed lines maximum and note truncation in returned data; verify no write HTTP methods are used
- [ ] T050 [US5] Implement `pr_review.analyze_pr(pr_data, vault_context, task_context)` in `orchestrator/agents/pr_review.py`: call Anthropic API with `claude-sonnet-4-6`; pass PR metadata, diff (truncated if needed), and vault context from Research Agent; return structured `PRReview` dict matching `data-model.md` PRReview entity; always set `human_review_required: true`
- [ ] T051 [US5] Update `orchestrator/utils/inbox_parser.py` to extract `pr_url` or `pr_number` and `repo` from the task request body when `agents: pr_review` is present; parse GitHub URL pattern `https://github.com/{owner}/{repo}/pull/{number}` to extract `repo` and `pr_number`
- [ ] T052 [US5] Update `orchestrator/agents/orchestrator.py` routing logic to include `pr_review` in `agents_to_run` when inbox task type is `pr_review`; pass `pr_url`/`pr_number` and `repo` fields through to the PR Review Agent
- [ ] T053 [US5] Add `GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}` environment variable to the `run-jarvis` job in `.github/workflows/jarvis.yml`; add a note in the workflow that this token must be scoped to `repo:read` only

**Phase 7 complete when**: Quickstart Sprint 5 scenario passes — PR review appears in vault with all required sections, flagged `[HUMAN REVIEW REQUIRED]`, and no GitHub API write calls were made.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T054 Add `validation:` section to `config/settings.yaml` with configurable thresholds: `pass_threshold: 0.90`, `retry_min_threshold: 0.60`, `low_sample_ci_threshold: 5`, `stale_record_days: 90`
- [ ] T055 [P] Update nightly digest in `orchestrator/agents/obsidian_writer.py` to include a "Run Quality Summary" section: table of agents with confidence scores, pass/fail status, and any escalations for the current run
- [ ] T056 [P] Update `orchestrator/agents/obsidian_writer.py` to write `jarvis/ci/` and `jarvis/vault/` paths to the `files[]` webhook payload when those directories exist and have new content
- [ ] T057 Add `pm_workflow_root: "PM"` and `jarvis_root: "Jarvis"` to `power_automate:` section in `config/settings.yaml`; update `orchestrator/utils/power_automate.py` to prefix all vault paths with `jarvis_root` value when constructing SharePoint paths
- [ ] T058 [P] Register new Phase 2 agents in `prompts/library.json`: add entries for `validation`, `ci_agent`, `vault_maintenance`, `pr_review` with `status: "approved"`, empty performance metrics, and correct file paths
- [ ] T059 Add timeout entries to `config/settings.yaml` for new agents: `validation_seconds: 30`, `ci_agent_seconds: 180`, `vault_maintenance_seconds: 120`, `pr_review_seconds: 120`
- [ ] T060 Write unit tests in `tests/test_run_logger.py`: test `start_run` creates valid JSON, `log_agent_entry` appends correctly, `finalize_run` sets correct fields, malformed entry handled gracefully
- [ ] T061 [P] Write unit tests in `tests/test_validation.py`: test composite score formula, three-tier threshold logic, synthetic pass on crash, compliance=0.0 on PII detection

**Phase 8 complete when**: All config values are settable from `settings.yaml` without code changes, digest includes quality summary, new agents are registered in `library.json`, unit tests pass.

---

## Dependencies Summary

```
T001–T007  (Phase 1 Setup)
    ↓
T008–T011  (Phase 2 Foundational)
    ↓
T012–T018  (Phase 3: US1 Logging)
    ↓
T019–T027  (Phase 4: US2 Validation)
    ↓
T028–T037  (Phase 5: US3 CI Agent)    ─┐
T038–T046  (Phase 6: US4 Vault Maint) ─┤ Can run in parallel
T047–T053  (Phase 7: US5 PR Review)   ─┘
    ↓
T054–T061  (Phase 8: Polish)
```

### Parallel Opportunities Within Phases

**Phase 1** (T001–T007): T001–T004 are fully parallel (different agent files). T006–T007 are parallel with T001–T005.

**Phase 3** (T012–T018): T012, T013, T014 are parallel (separate `run_logger` functions). T015 and T016 depend on T012–T014. T017 and T018 are parallel with T015–T016.

**Phase 4** (T019–T027): T019 (prompt) and T020 (stub) are parallel. T021 and T022 depend on T020. T023 depends on T019–T022. T024–T027 depend on T023.

**Phase 5** (T028–T037): T028 (prompt) and T029 (stubs) are parallel. T030–T034 are partially parallel (different functions in same file). T035 depends on T030–T034. T036–T037 depend on T035.

**Phase 6** (T038–T046): T038 (prompt) and T039 (stubs) are parallel. T040–T044 are partially parallel. T045 depends on T038–T044. T046 depends on T045.

**Phase 7** (T047–T053): T047 (prompt) and T048 (stubs) are parallel. T049–T050 depend on T048. T051–T052 are parallel with T049–T050. T053 is parallel with T047–T052.

---

## Implementation Strategy

**MVP Scope (Sprint 1 = US1 only)**: Complete Phase 1 + Phase 2 + Phase 3. This gives full observability without changing any existing agent behavior. Every subsequent sprint adds value incrementally with no risk to what's already working.

**Sprint boundaries**:
- Sprint 1 end: JSON logs in SharePoint after every run
- Sprint 2 end: Quality gates live; digest includes validation scores
- Sprint 3 end: First CI report in vault; prompt library initialized
- Sprint 4 end: Vault auto-fix commits running weekly
- Sprint 5 end: PR reviews on demand via inbox

**Zero-regression rule**: Phases 3–8 must not change the behavior of Phase 1 agents for valid inputs. Use `--dry-run` flag to test new code paths before enabling in production runs.

---

## Total Task Count

| Phase | Tasks | User Story |
|-------|-------|------------|
| Phase 1: Setup | 7 (T001–T007) | — |
| Phase 2: Foundational | 4 (T008–T011) | — |
| Phase 3: US1 Logging | 7 (T012–T018) | US1 |
| Phase 4: US2 Validation | 9 (T019–T027) | US2 |
| Phase 5: US3 CI Agent | 10 (T028–T037) | US3 |
| Phase 6: US4 Vault Maint | 9 (T038–T046) | US4 |
| Phase 7: US5 PR Review | 7 (T047–T053) | US5 |
| Phase 8: Polish | 8 (T054–T061) | — |
| **Total** | **61** | |
