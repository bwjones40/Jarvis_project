# Tasks: Jarvis MVP — AI Command Center

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Data Model**: [data-model.md](data-model.md)
**Generated**: 2026-06-13
**Total tasks**: 41

---

## User Story Map

| Story | Description | Spec Scenarios | FRs | Phase |
|-------|-------------|----------------|-----|-------|
| US1 | Overnight Task Execution | Primary Flow, Draft Staging, Clarification | FR-01–FR-13, FR-17–FR-20 | 3 |
| US2 | GCP Data Discovery (Daytime) | GCP Discovery | FR-14–FR-16 | 4 |
| US3 | Cost Controls & Token Visibility | Weekly cost rollup | FR-21–FR-23 | 5 |

---

## Phase 1: Setup

**Goal**: Working repo structure with GitHub Actions wired and triggering.

**Independent test criteria**: Push a change to `jarvis/inbox.md`; GitHub Actions workflow triggers and completes green. A test file appears in Obsidian via OneDrive (Power Automate smoke test).

- [ ] T001 Create repo directory structure: `orchestrator/agents/`, `orchestrator/utils/`, `prompts/`, `config/`, `tests/`, `jarvis/`, `.github/workflows/`
- [ ] T002 Create `jarvis/inbox.md` with template content from [inbox-schema contract](contracts/inbox-schema.md)
- [ ] T003 Create `config/settings.yaml` with model routing table (Orchestrator→`claude-sonnet-4-6`, subagents→`claude-haiku-4-5`) and agent timeout settings
- [ ] T004 Create `.github/workflows/jarvis.yml` with `on: push: paths: ['jarvis/inbox.md']` trigger, `on: schedule: cron: '0 23 * * 1-5'` nightly trigger, Python setup step, and `orchestrator/main.py` run step
- [ ] T005 Create `requirements.txt` with: `anthropic`, `google-cloud-bigquery`, `requests`, `pyyaml`

---

## Phase 2: Foundational

**Goal**: All shared utilities implemented and importable. Entry point parses args. No agent calls yet.

**Independent test criteria**: `python orchestrator/main.py --dry-run` exits 0, prints parsed task dict from a test `inbox.md`.

- [ ] T006 [P] Implement `utils/inbox_parser.py`: parse `jarvis/inbox.md` per [inbox-schema contract](contracts/inbox-schema.md); return `Task` dict or raise `InboxParseError` with human-readable message; handle empty file (return `None`), missing required fields, invalid priority/mode enum values
- [ ] T007 [P] Implement `utils/vault_reader.py`: `read_note(vault_path)` reads a file by vault-relative path; `search_notes(query, vault_root)` returns top-3 most relevant notes by keyword match on filename and H1 heading; `note_exists(vault_path)` checks presence before write
- [ ] T008 [P] Implement `utils/token_logger.py`: `log_agent_run(agent_name, model, usage, duration, output, errors)` returns `AgentRun` dict per [task-result schema](contracts/task-result-schema.md); `calculate_cost(agent_runs)` applies pricing table (Sonnet 4.6: $3/$15 per M in/out; Haiku 4.5: $0.80/$4 per M in/out); returns float
- [ ] T009 [P] Implement `utils/power_automate.py`: `post_files(files, run_metadata, webhook_url)` sends POST per [webhook-payload contract](contracts/webhook-payload.md); retry up to 3 times on 429/5xx with 30s backoff; logs error to `jarvis/run-errors.log` if all retries fail; returns `True` on success
- [ ] T010 Create `orchestrator/main.py` entry point: parse `--mode overnight|daytime` arg; load `config/settings.yaml`; call inbox parser; print parsed task or "No task in inbox"; stub for agent pipeline (not wired yet); `--dry-run` flag skips all API calls and PA webhook

---

## Phase 3: US1 — Overnight Task Execution

**Goal**: Full overnight pipeline: inbox → orchestrator → research → obsidian → vault files appear in Obsidian via Power Automate.

**Independent test criteria**: Run [Scenario 1](quickstart.md#scenario-1-overnight-task-execution-primary-flow) from quickstart.md. All 5 pass criteria met: workflow green, task file in vault, digest file exists, inbox cleared, token table populated. Also run [Scenario 2](quickstart.md#scenario-2-draft-communication-staging-safety-check) and [Scenario 3](quickstart.md#scenario-3-power-automate-webhook-output-pipeline).

### System Prompts

- [ ] T011 [US1] Create `prompts/orchestrator.md`: system prompt for Orchestrator — role (parse task, route to subagents, aggregate outputs), PII hard stop ("Never store, repeat, or process names, email addresses, or customer data. If the task contains PII, flag it in clarifications_needed and do not process the PII."), routing rules (route to `research` if context needed, `gcp` if data discovery, always route to `obsidian`), output format (structured JSON per TaskResult schema)
- [ ] T012 [P] [US1] Create `prompts/research.md`: system prompt for Research Agent — role (retrieve vault context, summarize findings), PII hard stop, instruction to check vault before generating new content, output format (context summary + source vault paths + `cache_hit: true/false`)
- [ ] T013 [P] [US1] Create `prompts/obsidian_writer.md`: system prompt for Obsidian Knowledge Agent — role (write task records, update evergreen notes, write digest, append lessons), PII hard stop, evergreen rules (update in place, never duplicate), cross-link format (`[[note-title]]`), draft communication flagging rule (`[HUMAN APPROVAL REQUIRED]` prefix on all draft messages)

### Core Agents

- [ ] T014 [US1] Implement `agents/orchestrator.py`: load system prompt from `prompts/orchestrator.md`; call Claude API with task dict + top-3 vault notes as context; parse response into TaskResult skeleton; determine agent routing sequence from `agents_needed` + orchestrator judgment; log own AgentRun via `token_logger`; pass TaskResult forward to subagents
- [ ] T015 [P] [US1] Implement `agents/research.py`: load system prompt from `prompts/research.md`; call `vault_reader.search_notes(task.request)` first — if result confidence > threshold, return vault content directly with `cache_hit: true` and zero API tokens; otherwise call Claude API with task + vault search results; append ResearchAgentRun to TaskResult; return updated TaskResult
- [ ] T016 [US1] Implement `agents/obsidian_writer.py` — task record writer: accept complete TaskResult dict; generate `jarvis/tasks/task-NNN-<slug>.md` content per [task-record format](contracts/task-result-schema.md#vault-markdown-format-persisted-task-record); include token usage table and estimated cost from `token_logger.calculate_cost()`; return file content as string (not written to disk — sent via PA)
- [ ] T017 [US1] Implement nightly digest generator in `agents/obsidian_writer.py`: generate `jarvis/digests/YYYY-MM-DD.md` content per [NightlyDigest entity](data-model.md#entity-nightlydigest); include tasks completed, token totals, knowledge notes updated, key learnings, draft communications pending, open questions; if no tasks ran, write "No tasks assigned today"
- [ ] T018 [US1] Implement lesson file appender in `agents/obsidian_writer.py`: generate AgentLesson entry per [entity spec](data-model.md#entity-agentlesson) for each agent in TaskResult; append-only format (do not overwrite existing content); return list of `{vault_path, content}` dicts for each lesson file
- [ ] T019 [US1] Implement knowledge note updater in `agents/obsidian_writer.py`: call Claude API with current note content + task output; generate updated note content; enforce evergreen rule by calling `vault_reader.note_exists()` before constructing write payload; call `vault_reader.read_note()` to get current content as input to Claude; log KnowledgeNote updates in TaskResult
- [ ] T020 [US1] Wire full sequential pipeline in `orchestrator/main.py`: Orchestrator → Research (if needed) → GCP (if needed, daytime only) → Obsidian; collect all file write payloads from Obsidian agent; call `power_automate.post_files()`; on success, clear `jarvis/inbox.md` to template and commit via `git commit -am "jarvis: clear inbox after task-NNN"` in workflow step

### Safety & Compliance

- [ ] T021 [US1] Add draft communication detection and staging in `agents/obsidian_writer.py`: scan all agent outputs for intent to send a message (keywords: "email", "Teams", "send", "notify", "message to"); extract as `DraftCommunication` entity per [data model](data-model.md#entity-draftcommunication); prepend `[HUMAN APPROVAL REQUIRED]` to all draft bodies; include in digest under "Draft Communications" section; confirm zero send capability exists in codebase
- [ ] T022 [P] [US1] Add clarification handling in `agents/orchestrator.py`: if task is ambiguous, populate `clarifications_needed` in TaskResult; Obsidian agent writes these to digest under "Open Questions"; inbox is still cleared (task is archived with `status: needs_clarification`); Orchestrator does not halt — it produces whatever output it can

### Integration & Workflow

- [ ] T023 [US1] Add connectivity check step to `.github/workflows/jarvis.yml`: verify `ANTHROPIC_API_KEY` is set and non-empty; make a lightweight status check call to confirm API reachability; fail fast with actionable error message if check fails
- [ ] T024 [US1] Implement PA smoke-test in `.github/workflows/jarvis.yml`: after main run, if `POWER_AUTOMATE_WEBHOOK_URL` is set, send a 1-file test POST via `power_automate.py`; log success/failure; do not fail the workflow if PA is unreachable (log warning instead)
- [ ] T025 [US1] Validate PII guard end-to-end: run [Scenario 6](quickstart.md#scenario-6-pii-guard-compliance) from quickstart.md manually; confirm neither name nor email address from the test task appears in any vault file written; document pass/fail in a comment on this task

---

## Phase 4: US2 — GCP Data Discovery (Daytime)

**Goal**: Operator can trigger GCP agent manually from CLI and receive a plain-English answer about BigQuery data.

**Independent test criteria**: Run [Scenario 4](quickstart.md#scenario-4-gcp-discovery-daytime-run) from quickstart.md. Output contains at least one dataset name in plain English; no raw SQL or schema JSON; no data modified.

- [ ] T026 [US2] Create `prompts/gcp_discovery.md`: system prompt for GCP Discovery Agent — role (translate vague data questions into BigQuery discoveries), plain-English output requirement ("Never include raw SQL, JSON schemas, or field-level technical details in your response"), read-only constraint ("You have read-only access; do not attempt to write, delete, or modify any data"), PII hard stop
- [ ] T027 [US2] Implement `agents/gcp_discovery.py`: accept vague data request string; run `bq ls --format=json` via `subprocess.run()` (read-only); run `bq show --schema {dataset}.{table}` for relevant tables; pass raw JSON output to Claude API with GCP system prompt; return plain-English summary as string; log AgentRun with token counts; never expose raw subprocess output to vault
- [ ] T028 [US2] Add `--mode daytime` flag and GCP routing to `orchestrator/main.py`: when `--mode daytime` and `gcp` in `agents_needed`, call `gcp_discovery.py` after Orchestrator; pass GCP output into Obsidian agent context before writing vault
- [ ] T029 [US2] Add overnight guard in `agents/orchestrator.py`: if `mode == overnight` and `gcp` in agents_needed, log "GCP agent skipped: overnight mode, service account not provisioned" in TaskResult; set `gcp` AgentRun status to `skipped`; continue pipeline without GCP output

---

## Phase 5: US3 — Cost Controls & Token Visibility

**Goal**: Every task file has a readable token usage table with cost estimate. Weekly digest includes a cost rollup. Vault caching reduces redundant API calls.

**Independent test criteria**: Run 3 tasks (any type). Each task file in `jarvis/tasks/` has a populated token table with estimated cost. The nightly digest for the third day includes a 7-day cost rollup section.

- [ ] T030 [US3] Update `utils/token_logger.py` with pricing table and cost calculator: `PRICING = {"claude-sonnet-4-6": {"input": 3.0, "output": 15.0}, "claude-haiku-4-5": {"input": 0.80, "output": 4.0}}`; `calculate_cost(agent_runs)` sums across all agents using per-million-token rates; returns formatted string e.g. `"$0.09"`
- [ ] T031 [US3] Update task record generator in `agents/obsidian_writer.py`: include token usage markdown table (columns: Agent, Model, Input Tokens, Output Tokens, Duration, Cost) plus total row; pull cost from `token_logger.calculate_cost(task_result['agents_executed'])`
- [ ] T032 [US3] Add weekly cost rollup to nightly digest in `agents/obsidian_writer.py`: call `vault_reader` to read all task files from last 7 days in `jarvis/tasks/`; sum token counts and cost estimates; write "## Weekly Usage" section to digest with: total runs, total tokens, total estimated cost, most expensive agent
- [ ] T033 [US3] Implement context pruning in `agents/orchestrator.py`: cap `vault_reader.search_notes()` results at 3 notes; truncate each note to 2,000 tokens before passing to Claude (split at paragraph boundary, not mid-sentence); log truncation in AgentRun output if it occurs
- [ ] T034 [US3] Add vault cache-hit logging to `agents/research.py`: when returning cached vault content (zero API tokens), set `cache_hit: true` in AgentRun output and `input_tokens: 0, output_tokens: 0`; include in weekly digest as "Cache hits this week: N" metric

---

## Phase 6: Polish & Cross-Cutting Concerns

**Goal**: Test coverage for critical utilities, operator-facing documentation, final compliance check.

- [ ] T035 Create `tests/test_inbox_parser.py`: unit tests for `InboxParser` — valid task parses correctly, missing `Request` section raises `InboxParseError`, invalid `Priority` value raises error, empty file returns `None`, multiple tasks returns first and logs warning
- [ ] T036 [P] Create `tests/test_orchestrator.py`: unit tests for agent routing logic — task with `research` in agents_needed routes to Research Agent, task with `gcp` in overnight mode skips GCP Agent, TaskResult structure matches schema
- [ ] T037 [P] Create `tests/test_gcp_discovery.py`: unit tests for GCP agent with mocked `subprocess.run()` — confirms no raw JSON passed to Claude, confirms output is plain English, confirms no writes attempted
- [ ] T038 [P] Create `tests/test_obsidian_writer.py`: unit tests — evergreen rule (existing note updated not duplicated), draft communication flagged with `[HUMAN APPROVAL REQUIRED]`, digest generated correctly when no tasks ran
- [ ] T039 [P] Create `tests/test_power_automate.py`: unit tests with mocked `requests.post()` — retry logic triggers on 429, success returns `True`, all-retries-exhausted writes to `run-errors.log`
- [ ] T040 Create `jarvis/README.md`: operator quickstart (how to assign a task, what to expect in Obsidian, how to approve draft communications, how to trigger GCP agent manually); link to [quickstart.md](quickstart.md)
- [ ] T041 Run [Scenario 5](quickstart.md#scenario-5-nightly-digest-cron-trigger) from quickstart.md: verify cron trigger fires on schedule and digest appears in vault even when no task was assigned; document pass/fail

---

## Dependency Graph

```
Phase 1 (Setup)
  └── Phase 2 (Foundational utilities)
        ├── Phase 3 (US1 - Overnight Execution)  ← MVP complete here
        │     ├── Phase 4 (US2 - GCP Discovery)
        │     └── Phase 5 (US3 - Cost Controls)
        │           └── Phase 6 (Polish)
        └── Phase 4 can start in parallel with Phase 5
```

**Stories are mostly sequential** due to shared agent pipeline: US2 and US3 both build on top of the US1 orchestration backbone. Phase 4 and Phase 5 can run in parallel once Phase 3 is complete.

---

## Parallel Execution Opportunities

### Within Phase 2 (all utilities are independent files):
```
T006 (inbox_parser.py) ─┐
T007 (vault_reader.py)  ─┤── all parallelizable
T008 (token_logger.py)  ─┤
T009 (power_automate.py)─┘
T010 (main.py)           ← depends on T006–T009 (must run after)
```

### Within Phase 3 (system prompts are independent):
```
T011 (orchestrator.md) ─┐
T012 (research.md)      ─┤── all parallelizable
T013 (obsidian.md)      ─┘
T014 (orchestrator.py)   ← depends on T011
T015 (research.py)       ← depends on T012, can parallel with T016–T019
T016–T019 (obsidian_writer.py)  ← T014 must precede T016 (needs TaskResult structure)
T021, T022               ← parallelizable with each other
```

### Phase 4 + Phase 5 (independent stories, parallel after Phase 3):
```
Phase 4 (US2): T026→T027→T028→T029
Phase 5 (US3): T030→T031→T032→T033→T034
```

### Within Phase 6 (all test files are independent):
```
T036, T037, T038, T039 ── all parallelizable
```

---

## MVP Scope

**Suggested MVP**: Complete Phases 1–3 (Tasks T001–T025).

This delivers the full overnight pipeline: inbox parsing, orchestration, research, knowledge writing, Power Automate output, nightly digest, draft communication safety, and audit logging. The operator can assign tasks and read results in Obsidian the next morning.

Phases 4–6 extend the system with GCP discovery, cost controls, and test coverage — valuable but not required for first operational use.

---

## Implementation Strategy

1. **Start with the plumbing** (Phase 1–2): Get GitHub Actions triggering and a test file appearing in Obsidian before writing any agent logic. This validates the full infrastructure stack early.

2. **Build agents bottom-up** (Phase 3): Implement the Obsidian writer first with hardcoded test input, then Research, then Orchestrator. This way each layer can be validated independently before being wired together.

3. **Smoke test with real API** before Phase 4: Run Scenario 1 end-to-end once the full US1 pipeline is wired. Fix any token budget or prompt issues before adding more agents.

4. **GCP and cost controls are additive** (Phase 4–5): They extend the existing pipeline without modifying core orchestration logic. Safe to implement one at a time.
