# Feature Specification: Jarvis MVP — AI Command Center

**Feature ID**: 001-jarvis-mvp
**Created**: 2026-06-13
**Status**: Draft

---

## Overview

An internal AI orchestration system ("Jarvis") that autonomously executes assigned tasks overnight and delivers results to the operator via their Obsidian knowledge vault each morning. The system operates within enterprise safety constraints, never sending external communications without human approval, and grows smarter over time by writing what it learns back into a living knowledge base.

### Problem Statement

The operator spends significant daytime hours on research, knowledge retrieval, and data discovery tasks that could be delegated to an autonomous agent running overnight. Without this system, context is lost between sessions, repetitive queries are re-answered from scratch, and no persistent organizational memory exists across the operator's work.

### Proposed Solution

A task orchestration system that:
1. Accepts task assignments via a simple text file the operator edits and commits
2. Executes those tasks autonomously using a hierarchy of specialized subagents
3. Writes results and learned knowledge back to the operator's Obsidian vault
4. Produces a morning digest so the operator starts each day with completed work waiting

---

## Actors

| Actor | Role |
|-------|------|
| Operator (You) | Assigns tasks, reads morning digests, approves any external communications |
| Orchestrator Agent | Parses tasks, routes to subagents, aggregates outputs |
| Research Agent | Retrieves relevant context from the knowledge vault and prior decisions |
| GCP Discovery Agent | Answers data discovery questions using read-only access to BigQuery |
| Obsidian Knowledge Agent | Writes all outputs to the vault and produces the nightly digest |

---

## User Scenarios & Testing

### Primary Flow: Overnight Task Execution

1. Operator edits the task inbox file with a plain-language request before end of day
2. System detects the new task and begins execution
3. Orchestrator determines which subagents are needed and sequences them
4. Each subagent executes its portion and returns structured results
5. Obsidian Agent writes outputs to the vault and appends to the nightly digest
6. Operator opens Obsidian the next morning and finds completed work in the digest

**Acceptance**: Task assigned Monday evening is fully processed and readable in the vault Tuesday morning without operator intervention.

### Secondary Flow: GCP Data Discovery (Daytime)

1. Operator receives a vague data request (e.g., from a colleague's email)
2. Operator triggers the GCP Discovery Agent manually with the request
3. Agent queries BigQuery metadata (read-only) and translates findings into plain English
4. Output includes: exact table names, dataset locations, and sample query instructions
5. Operator can share the plain-English output with the original requester

**Acceptance**: Vague "where is the data on X?" question produces a specific, actionable answer without the operator needing to know BigQuery schema details.

### Edge Case: External Communication Required

1. Task output includes a draft email or Teams message
2. System flags the draft with `[HUMAN APPROVAL REQUIRED]` marker
3. Draft is written to the vault but not sent
4. Operator reviews and sends manually if approved

**Acceptance**: No external message (email, Teams) is ever sent automatically. All such outputs are drafts only.

### Edge Case: Task Requires Clarification

1. Task description is ambiguous or missing required context
2. Orchestrator includes a `[NEEDS CLARIFICATION: ...]` note in the task output
3. Output is still written to the vault with what was completed
4. Operator can refine the task and resubmit

---

## Functional Requirements

### Task Assignment

- **FR-01**: The system accepts task assignments via a plaintext inbox file that the operator edits directly
- **FR-02**: Tasks specify at minimum: a short title, priority level, execution mode (overnight or daytime), and a plain-language request
- **FR-03**: The system triggers automatically when a new task is committed to the inbox file
- **FR-04**: The system also runs on a nightly schedule even if no new tasks are present (to produce the digest)
- **FR-05**: Completed tasks are archived with a timestamp; the inbox is cleared after each run

### Task Orchestration

- **FR-06**: The Orchestrator reads the inbox task and determines which subagents are needed
- **FR-07**: The Orchestrator passes relevant knowledge context (top 3 most relevant vault notes) to each subagent to reduce redundant API calls
- **FR-08**: Subagents execute sequentially; each receives the structured output of the previous agent
- **FR-09**: The Orchestrator aggregates all subagent outputs into a single structured task result

### Knowledge Management

- **FR-10**: All task results are written to the vault as a permanent task record
- **FR-11**: The Obsidian Agent updates evergreen knowledge notes in place (never creates duplicates for the same topic)
- **FR-12**: Each agent appends to its own lesson file after every run: what failed, what worked, patterns to reuse
- **FR-13**: A nightly digest file is written to the vault each day, summarizing all completed tasks and key learnings

### GCP Data Discovery

- **FR-14**: The GCP Discovery Agent operates in read-only mode; it has no write credentials to any data system
- **FR-15**: Agent output is always in plain English — no raw query syntax or technical schema details exposed to the operator
- **FR-16**: The agent runs only when triggered by the operator during daytime hours (not overnight) until a service account is provisioned

### Safety & Compliance

- **FR-17**: The system never stores or processes personally identifiable information (names, emails, customer data)
- **FR-18**: Any output that includes a message intended for another person is written as a draft flagged `[HUMAN APPROVAL REQUIRED]` and never sent automatically
- **FR-19**: Every task run is logged with: task ID, agents used, models used, token counts, and timestamp
- **FR-20**: All system access to external services is read-only during the MVP

### Cost Controls

- **FR-21**: Token usage per agent is logged to each task file
- **FR-22**: The weekly digest includes a cost summary: total tokens, estimated cost per workflow, most expensive agents
- **FR-23**: If the answer to a question exists in the knowledge vault, the system uses that rather than making an API call

---

## Success Criteria

| Criterion | Measure |
|-----------|---------|
| Autonomous overnight execution | Operator assigns task before end of day; completed output is in vault before 8 AM the next morning, zero operator interaction required |
| Morning digest reliability | A nightly digest file exists in the vault every weekday morning |
| Zero unauthorized external sends | No email or Teams message is sent by the system without operator explicitly sending a pre-written draft |
| GCP discovery accuracy | Agent correctly identifies relevant BigQuery dataset/table for a known data request, confirmed by operator |
| Knowledge accumulation | After 30 days, at least 10 evergreen knowledge notes exist and are referenced by subsequent task runs |
| Cost visibility | Operator can determine the estimated cost of any completed task run from its task file within 60 seconds |
| PII-free operation | Zero instances of PII appearing in vault files or task logs over the MVP period |

---

## Assumptions

- The operator has a GitHub repository where the inbox file and workflow definitions are stored
- The operator has access to a Power Automate environment with standard SharePoint and HTTP connectors
- Claude Enterprise API access is available and the API key can be stored securely as a workflow secret
- Obsidian vault is synced via OneDrive, making SharePoint-written files available locally
- GCP BigQuery access requires a service account that is not yet provisioned; daytime-only runs use the operator's existing authenticated session
- The vault's `jarvis/` folder is treated as system-managed; the operator does not manually edit files inside it

---

## Constraints & Dependencies

| Constraint | Impact |
|------------|--------|
| No PII handling | Agent prompts must include an explicit hard stop on storing or processing personal data |
| Human approval for external sends | All draft communications must be written to vault; no auto-send capability |
| GCP service account not yet provisioned | GCP Discovery Agent is daytime-only for MVP; overnight capability is deferred |
| Enterprise-approved services only | System may only use: Claude Enterprise API, GitHub, Power Automate, SharePoint |
| Read-only GCP access | Agent can discover and describe data but cannot modify any data system |

---

## Out of Scope (MVP)

- PR Review Agent
- Ad hoc request intake from Outlook or Teams
- Validation Agent (regression testing)
- Autonomous Copilot delegation
- Overnight GCP Discovery Agent runs
- Any compute migration to GCP or Azure

---

## Key Entities

| Entity | Description |
|--------|-------------|
| Task | A unit of work assigned by the operator, with priority, mode, and a plain-language request |
| Inbox File | The single file the operator edits to assign tasks; cleared after each run |
| Task Record | Permanent archive of a completed task: inputs, outputs, agents used, tokens, timestamp |
| Nightly Digest | Daily summary file written to the vault each night |
| Evergreen Note | A living knowledge note that is updated in place (GCP datasets, project context, team info) |
| Agent Lesson File | Per-agent log of what worked, what failed, and reusable patterns |
| Draft Communication | A system-generated message flagged for human review before sending |
