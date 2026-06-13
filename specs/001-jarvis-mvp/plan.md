# Implementation Plan: Jarvis MVP — AI Command Center

**Created**: 2026-06-13
**Feature**: [spec.md](spec.md)
**Research**: [research.md](research.md)
**Data Model**: [data-model.md](data-model.md)

---

## Technical Context

| Item | Decision |
|------|----------|
| Language | Python 3.12 |
| Agent execution | Sequential function calls; no async framework |
| Claude API | `anthropic` Python SDK, direct Enterprise API |
| Orchestrator model | `claude-sonnet-4-6` |
| Subagent model | `claude-haiku-4-5` |
| CI/CD | GitHub Actions (`ubuntu-latest` hosted runner) |
| Vault output | Power Automate webhook → SharePoint → OneDrive → Obsidian |
| Config | `config/settings.yaml` — model routing, agent settings |
| Secrets | GitHub Actions secrets: `ANTHROPIC_API_KEY`, `POWER_AUTOMATE_WEBHOOK_URL` |
| GCP access | Operator `gcloud auth` (daytime only); service account deferred |

**Open item**: SharePoint site URL and document library path must be confirmed by operator before Power Automate flow can be finalized. Does not block Phase 1 or Phase 2 implementation.

---

## Architecture Decisions

### Sequential Agent Pipeline
Agents execute in a fixed sequence: Orchestrator → Research → [GCP if needed] → Obsidian. Each agent receives the cumulative context dict (TaskResult) and appends its output before passing it forward. This is simpler than parallel execution and matches the data dependencies (Obsidian needs all other agents' outputs to write the complete record).

### Inbox as the Only Input Interface
No REST API, no webhook intake, no email parsing in MVP. The operator edits one file. This minimizes attack surface, eliminates auth complexity, and is immediately usable.

### Vault as the Only Output Interface
No push notifications, no email, no Teams messages sent automatically. Everything lands in the vault. The operator reads the vault. This enforces the human-in-the-loop requirement structurally rather than through prompting alone.

### Knowledge Vault as Prompt Cache
Before any API call, the Research Agent checks the vault for an existing answer. If a high-confidence match exists, it returns the vault content directly without an API call. This reduces cost and latency for recurring question types.

---

## Constitution Check

No `.specify/memory/constitution.md` exists for this project. Governance constraints are drawn from [spec.md](spec.md) section "Constraints & Dependencies":

| Constraint | Gate Status | Mitigation |
|------------|-------------|------------|
| No PII handling | MUST enforce | Hard stop in every agent system prompt: "Never store, repeat, or process names, email addresses, or customer data." |
| Human approval for external sends | MUST enforce | DraftCommunication entity is write-only to vault; no send capability in codebase |
| Read-only GCP access | MUST enforce | GCP agent uses credentials with `bigquery.dataViewer` + `bigquery.jobUser` roles only; no write roles requested |
| Enterprise-approved services only | MUST enforce | Dependency list: `anthropic`, `google-cloud-bigquery`, `requests`, `pyyaml`. No unapproved SaaS SDKs. |
| Audit trail | MUST enforce | AgentRun logged for every execution; token counts required fields |

All gates pass. No constraint violations in the planned design.

---

## Implementation Phases

### Phase 1: Repo Skeleton + GitHub Actions

**Goal**: A working trigger that runs a no-op Python script and POSTs a test payload to Power Automate.

**Tasks**:
1. Create repo directory structure (see spec Section 10)
2. Create `jarvis/inbox.md` with template content
3. Create `.github/workflows/jarvis.yml`:
   - `on: push: paths: ['jarvis/inbox.md']`
   - `on: schedule: cron: '0 23 * * 1-5'` (11 PM weeknights)
   - Job: checkout, setup Python, run `orchestrator/main.py`
4. Create `orchestrator/main.py` stub: reads `jarvis/inbox.md`, prints parsed task, exits 0
5. Create `utils/power_automate.py`: POST function that sends webhook payload per [webhook-payload contract](contracts/webhook-payload.md)
6. Add connectivity check step to workflow: validate `ANTHROPIC_API_KEY` is set and non-empty
7. Wire up a smoke-test POST to Power Automate at end of workflow run (sends a test file to vault)

**Validation**: Push a change to `inbox.md`; confirm workflow triggers and a `jarvis/test.md` appears in Obsidian via OneDrive.

---

### Phase 2: Inbox Parser + Orchestrator Agent

**Goal**: Orchestrator correctly parses any valid task and produces a structured TaskResult skeleton.

**Tasks**:
1. Implement `utils/inbox_parser.py`:
   - Parse `jarvis/inbox.md` per [inbox schema contract](contracts/inbox-schema.md)
   - Return a `Task` dict or raise `InboxParseError` with human-readable message
   - Write parse errors to digest and exit gracefully (no stack traces in vault)
2. Implement `agents/orchestrator.py`:
   - System prompt: role definition, PII hard stop, routing rules
   - Input: Task dict + top-3 knowledge notes from vault
   - Output: TaskResult skeleton with `agents_executed[0]` (orchestrator's own run) populated
   - Routing logic: determine which agents to invoke based on `agents_needed` field
3. Implement `utils/vault_reader.py`:
   - Read vault notes by path
   - Search vault for relevant notes by keyword (simple filename + H1 match for MVP)
   - Return top-3 most relevant notes as context strings
4. Implement `utils/token_logger.py`:
   - Accept `anthropic.types.Usage` object
   - Return formatted AgentRun token fields
5. Wire Orchestrator into `main.py`

**Validation**: Run `main.py` locally against a test `inbox.md`. Confirm TaskResult JSON is printed to stdout with correct structure per [task-result schema](contracts/task-result-schema.md).

---

### Phase 3: Research Agent

**Goal**: Research Agent retrieves relevant vault context and returns a context summary.

**Tasks**:
1. Implement `agents/research.py`:
   - System prompt: knowledge retrieval role, PII hard stop
   - Input: Task description + vault search results
   - First checks vault via `vault_reader.py` before calling API
   - If vault hit confidence > 0.8: return vault content directly (zero API tokens)
   - Output: Context summary string + list of source vault paths
2. Update Orchestrator routing to call Research Agent when `research` in `agents_needed`
3. Pass Research output into subsequent agent contexts

**Validation**: Assign a task that asks about something already in the vault. Confirm Research Agent returns vault content without making an API call (check token count is 0 for that agent).

---

### Phase 4: Obsidian Knowledge Agent + Power Automate Integration

**Goal**: Every task run produces correctly formatted vault files posted to SharePoint.

**Tasks**:
1. Implement `agents/obsidian_writer.py`:
   - System prompt: vault writing role, evergreen rules, PII hard stop
   - Input: Complete TaskResult dict + current content of notes to be updated
   - Outputs (all as strings, not file writes): task record markdown, digest update, knowledge note diffs, lesson file append
   - Enforce evergreen rule: agent checks if note exists before creating; updates in-place if so
2. Implement digest writer: generates `jarvis/digests/YYYY-MM-DD.md` per data model spec
3. Implement lesson file appender: appends AgentLesson entry to `jarvis/agents/<name>-lessons.md`
4. Wire `power_automate.py` to collect all written files and POST in a single webhook call
5. After successful POST, clear `jarvis/inbox.md` (reset to template) and commit via `git` in the workflow
6. Handle PA webhook errors: retry up to 3 times with 30s backoff; write error to local `jarvis/run-errors.log` if all retries fail

**Validation**: Run Scenario 1 from [quickstart.md](quickstart.md). All 5 pass criteria must be met.

---

### Phase 5: GCP Discovery Agent (Daytime Only)

**Goal**: Operator can trigger the GCP agent manually and receive a plain-English data discovery output.

**Tasks**:
1. Implement `agents/gcp_discovery.py`:
   - System prompt: data discovery role, plain-English output requirement, PII hard stop, read-only constraint statement
   - Input: Vague data request string
   - Tool use: call `bq ls --project={project} --format=json` and `bq show --schema {dataset}.{table}` via subprocess
   - Output: Plain-language summary with dataset names, table names, and high-level descriptions
   - Never include raw SQL, schema JSON, or field-level details in output
2. Add `--mode daytime` flag to `main.py` to trigger GCP agent without cron/push trigger
3. Add guard: if not in daytime mode, skip GCP agent and log "GCP agent skipped: overnight mode, service account not provisioned"

**Validation**: Run Scenario 4 from [quickstart.md](quickstart.md).

---

### Phase 6: Cost Controls + Token Logging

**Goal**: Every task file has a readable token usage table; weekly digest includes cost summary.

**Tasks**:
1. Implement cost calculator in `utils/token_logger.py`:
   - Pricing table: Sonnet 4.6 = $3/$15 per M in/out tokens; Haiku 4.5 = $0.80/$4 per M in/out
   - Accept list of AgentRun dicts; return total cost as float
2. Update task record template to include token table (per [task-result schema](contracts/task-result-schema.md))
3. Update nightly digest to include weekly rollup (sum of all task files from last 7 days)
4. Add context pruning to Orchestrator: cap knowledge context at 3 notes, max 2,000 tokens per note
5. Add Research Agent cache hit logging: log `cache_hit: true/false` per run in AgentRun output

**Validation**: Run 3 tasks. Check that each task file has a token table. Check weekly digest shows cost rollup.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SharePoint path unknown | High | Blocks output pipeline | Operator confirms path before Phase 4; phases 1-3 unblocked |
| GCP service account delayed (4-8 weeks) | High | GCP agent overnight-only delayed | MVP scoped to daytime-only; no blocker |
| Power Automate throttling on burst writes | Low | Digest delayed | Retry logic with backoff in `power_automate.py` |
| Claude API rate limit on overnight run | Low | Task fails silently | Retry logic + error written to digest |
| Vault note conflicts (concurrent writes) | Very low | Knowledge corruption | Obsidian Agent is the sole writer; GitHub Actions is single-concurrent by default |
| PII leak in task output | Low | Compliance violation | Hard stop in every system prompt + PII guard validation (Scenario 6) |

---

## File Inventory

```
.github/workflows/jarvis.yml
jarvis/inbox.md
orchestrator/
  main.py
  agents/
    orchestrator.py
    research.py
    gcp_discovery.py
    obsidian_writer.py
  utils/
    token_logger.py
    vault_reader.py
    power_automate.py
    inbox_parser.py
prompts/
  orchestrator.md
  research.md
  gcp_discovery.md
  obsidian_writer.md
config/
  settings.yaml
tests/
  test_inbox_parser.py
  test_orchestrator.py
  test_gcp_discovery.py
  test_obsidian_writer.py
  test_power_automate.py
```
