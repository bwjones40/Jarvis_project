# Data Model: Jarvis MVP

**Created**: 2026-06-13
**Feature**: [spec.md](spec.md)

All entities are represented as markdown files in the Obsidian vault or as in-memory JSON dicts during agent execution. There is no database.

---

## Entity: Task

**Description**: A unit of work assigned by the operator via the inbox file.

**Source**: Parsed from `jarvis/inbox.md`

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `title` | string | yes | Non-empty, max 80 chars |
| `priority` | enum | yes | `high` \| `medium` \| `low` |
| `mode` | enum | yes | `overnight` \| `daytime` |
| `agents_needed` | list[string] | yes | One or more of: `orchestrator`, `research`, `gcp`, `obsidian` |
| `due` | string | no | ISO date or `"next run"` |
| `request` | string | yes | Non-empty plain-language description |
| `context` | string | no | Project name, requester, links |
| `copilot_handoff` | string | no | Manual handoff instructions for Copilot |

**State transitions**:
```
pending (in inbox.md)
  → in_progress (Orchestrator picks it up)
  → completed (written to jarvis/tasks/)
  → archived (inbox.md cleared)
```

---

## Entity: TaskResult

**Description**: The structured output of a completed task run. Passed between agents as a JSON dict; persisted to the vault as a markdown task record.

| Field | Type | Notes |
|-------|------|-------|
| `task_id` | string | Format: `task-NNN-<slug>` e.g. `task-001-gcp-discovery` |
| `task_title` | string | From input Task |
| `run_timestamp` | ISO 8601 datetime | UTC |
| `mode` | enum | `overnight` \| `daytime` |
| `status` | enum | `completed` \| `partial` \| `needs_clarification` |
| `agents_executed` | list[AgentRun] | In order of execution |
| `output_summary` | string | Plain-language summary for digest |
| `draft_communications` | list[DraftComm] | May be empty |
| `clarifications_needed` | list[string] | May be empty |
| `knowledge_updates` | list[string] | Vault paths updated by Obsidian Agent |

---

## Entity: AgentRun

**Description**: Per-agent execution record, embedded in TaskResult.

| Field | Type | Notes |
|-------|------|-------|
| `agent_name` | string | e.g. `orchestrator`, `research`, `gcp_discovery`, `obsidian` |
| `model` | string | e.g. `claude-sonnet-4-6`, `claude-haiku-4-5` |
| `input_tokens` | integer | |
| `output_tokens` | integer | |
| `duration_seconds` | float | Wall-clock time |
| `output` | string or dict | Agent-specific structured output |
| `errors` | list[string] | May be empty |

---

## Entity: KnowledgeNote

**Description**: An evergreen markdown file in the vault. Updated in-place by the Obsidian Agent; never duplicated.

| Field | Type | Notes |
|-------|------|-------|
| `path` | string | Vault-relative path e.g. `jarvis/knowledge/gcp/datasets.md` |
| `title` | string | H1 heading of the note |
| `topic` | string | Category: `gcp`, `project`, `team`, `pattern` |
| `last_updated` | ISO date | Updated by Obsidian Agent on each write |
| `referenced_by` | list[string] | Task IDs that cited this note |
| `content` | string | Full markdown content |

**Evergreen rules**:
- Obsidian Agent searches by `title` before writing — never creates a duplicate
- Updates are in-place edits, not appends (except for lesson files)
- Cross-links to related notes use Obsidian `[[note-title]]` syntax

---

## Entity: AgentLesson

**Description**: Append-only log per agent. Each run appends one entry.

| Field | Type | Notes |
|-------|------|-------|
| `run_date` | ISO date | |
| `task_id` | string | |
| `what_failed` | string | May be "nothing" |
| `what_worked` | string | Non-empty |
| `pattern_discovered` | string | Reusable insight; may be empty |
| `tokens_saved` | integer | vs. previous run on similar task; 0 if unknown |

**Vault path**: `jarvis/agents/<agent-name>-lessons.md`

---

## Entity: NightlyDigest

**Description**: Daily summary written to the vault each night.

| Field | Type | Notes |
|-------|------|-------|
| `date` | ISO date | |
| `tasks_completed` | list[string] | Task IDs and titles |
| `total_input_tokens` | integer | Sum across all agents |
| `total_output_tokens` | integer | Sum across all agents |
| `estimated_cost_usd` | float | Calculated from model pricing |
| `knowledge_notes_updated` | list[string] | Vault paths modified |
| `key_learnings` | list[string] | Bullet points from agent lesson files |
| `draft_communications` | list[DraftComm] | Any items awaiting human approval |
| `open_questions` | list[string] | Clarifications needed from operator |

**Vault path**: `jarvis/digests/YYYY-MM-DD.md`

---

## Entity: DraftCommunication

**Description**: A message intended for another person, staged for human approval. Never auto-sent.

| Field | Type | Notes |
|-------|------|-------|
| `draft_id` | string | UUID |
| `task_id` | string | Source task |
| `channel` | enum | `email` \| `teams` |
| `recipient` | string | Name only — no email address stored (PII rule) |
| `subject` | string | |
| `body` | string | Full draft content |
| `approval_status` | enum | Always `pending` when created |
| `flag` | string | Always `[HUMAN APPROVAL REQUIRED]` |

---

## Entity: InboxFile

**Description**: The operator-editable markdown file that drives task assignment.

**Invariants**:
- Contains at most one active task at a time (MVP)
- Cleared by the system after successful task archival
- Never modified by agents during execution — read-only input

**Vault path**: `jarvis/inbox.md`

---

## Relationships

```
Operator edits → InboxFile
InboxFile parsed → Task
Task executed → TaskResult
TaskResult contains → AgentRun[]
TaskResult contains → DraftCommunication[]
TaskResult triggers → KnowledgeNote updates
TaskResult triggers → AgentLesson append
TaskResult contributes to → NightlyDigest
NightlyDigest contains → DraftCommunication[] (pending approvals)
```
