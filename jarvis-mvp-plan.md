# Jarvis MVP Plan
_AI Command Center — Enterprise Operator + Subagent System_
_Last updated: 2026-06-13_

---

## 1. Goal

Build an internal AI orchestration system ("Jarvis") that:
- Works autonomously overnight on assigned tasks
- Reports results Monday morning via Obsidian vault digest
- Operates safely within enterprise constraints (no PII, human-in-the-loop for external sends)
- Grows smarter over time via a living knowledge base

---

## 2. Architecture Overview

```
YOU (daytime)
  └── edit jarvis/inbox.md → commit to GitHub repo
        └── GitHub Actions triggered
              └── Orchestrator Agent (Claude Enterprise API)
                    ├── Research Agent
                    ├── GCP Discovery Agent  [daytime only, your gcloud auth]
                    ├── Obsidian Knowledge Agent
                    └── Validation Agent
                          └── Power Automate webhook
                                └── writes digest to SharePoint vault
                                      └── OneDrive syncs to local Obsidian
                                            └── you read results Monday morning
```

### Communication Pattern
- **Input**: `jarvis/inbox.md` — task file you edit and commit
- **Output**: Obsidian vault digest + task outputs written to SharePoint via Power Automate
- **Agent-to-agent**: Sequential handoff, results passed as structured JSON between agents
- **Human checkpoints**: Any external send (email, Teams) is staged as a draft — never auto-sent

---

## 3. MVP Scope

### What to build first (MVP)
| Workflow | Mode | Blocker |
|---|---|---|
| Task Orchestration | Overnight autonomous | None |
| Obsidian Knowledge Agent | Overnight autonomous | None |
| GCP Discovery Agent | Daytime, user-triggered | Needs your active gcloud auth |

### Deferred to V2
- PR Review Agent (low daily volume)
- Ad Hoc Request Intake from Outlook/Teams (needs Power Automate + webhook endpoint)
- Validation Agent (depends on established baseline from MVP workflows)
- Autonomous Copilot delegation (needs Copilot Studio + Power Automate integration)

---

## 4. Agent Definitions

### Orchestrator Agent
- **Model**: Claude Sonnet 4.6 via Claude Enterprise API
- **Trigger**: New task committed to `jarvis/inbox.md`
- **Responsibilities**: Parse task, determine required subagents, sequence execution, aggregate outputs
- **Input**: Raw task from `inbox.md` + relevant Obsidian knowledge context
- **Output**: Structured JSON task result → passed to Obsidian Agent for storage

### Research Agent
- **Model**: Claude Haiku 4.5 via Claude Enterprise API
- **Trigger**: Called by Orchestrator when task requires background context
- **Responsibilities**: Search Obsidian vault for existing knowledge, summarize SharePoint docs, surface relevant prior decisions
- **Input**: Task description + search query
- **Output**: Context summary + source references

### GCP Discovery Agent
- **Model**: Claude Haiku 4.5 via Claude Enterprise API
- **Trigger**: User-initiated daytime runs only (requires active `gcloud auth`)
- **Responsibilities**: Run `bq ls` and schema queries via Google SDK CLI, identify relevant tables, translate findings into non-technical plain-language output
- **Input**: Vague data request (as received from email/Teams)
- **Output**: Exact table names, dataset locations, sample query instructions in plain English
- **Constraint**: Cannot run overnight until GCP service account is provisioned

### Obsidian Knowledge Agent
- **Model**: Claude Haiku 4.5 via Claude Enterprise API
- **Trigger**: End of every task run
- **Responsibilities**:
  - Write task outputs to vault
  - Update evergreen knowledge notes (GCP tables, project context, team info)
  - Update per-agent lesson files with any new errors or patterns discovered
  - Write nightly digest
- **Input**: Task result JSON + current vault note contents
- **Output**: Updated markdown files posted to SharePoint via Power Automate webhook

### Validation Agent (V2)
- **Model**: Claude Sonnet 4.6
- **Trigger**: After any code, query, or report is generated
- **Responsibilities**: Generate test cases from baseline behavior, detect regressions, produce Pass/Fail summary
- **Output**: Validation Summary (Pass/Fail, what changed, risks remaining)

---

## 5. Obsidian Vault Structure

Jarvis owns the `jarvis/` folder entirely. Do not manually edit files inside it — Jarvis manages them.

```
vault/
  jarvis/
    inbox.md                    ← YOU edit this to assign tasks
    digests/
      2026-06-13.md             ← nightly summary (one file per day)
    tasks/
      task-001-gcp-discovery.md ← one file per completed task
    knowledge/
      gcp/
        datasets.md             ← evergreen: known GCP datasets + table schemas
        aprilia-context.md      ← tribal knowledge from team conversations
      projects/
        [project-name].md       ← one evergreen file per active project
      team/
        contacts.md             ← who knows what (e.g., Aprilia owns GCP schema)
    agents/
      orchestrator-lessons.md   ← common errors + what fixed them
      gcp-agent-lessons.md
      research-agent-lessons.md
      obsidian-agent-lessons.md
    patterns/
      gcp-query-templates.md    ← reusable query patterns that worked
      prompt-templates.md       ← prompts that performed well
```

### Karpathy Wiki Principles (applied to this vault)
- **Evergreen**: Notes update in place — never create a new note for a topic that already has one
- **Atomic**: One concept per note (one dataset, one project, one agent)
- **Cross-linked**: Every note references related notes by name
- **Agent lesson files**: Each agent appends to its lesson file after every run:
  - What failed and why
  - What worked better than expected
  - Token optimization discovered
  - A pattern to reuse next time

---

## 6. Task File Format (`jarvis/inbox.md`)

```markdown
# Jarvis Inbox

## Task: [short title]
**Priority**: high | medium | low
**Mode**: overnight | daytime
**Agents needed**: orchestrator, research, gcp, obsidian
**Due**: [date or "next run"]

### Request
[Plain language description of what you want done.
Be as vague or specific as you want — Jarvis will ask clarifying
questions in the output if it needs more context.]

### Context
[Optional: relevant project name, who asked, links to SharePoint docs]

### Copilot handoff
[Optional: if part of this task should be handed to Copilot manually,
describe what and why here]

---
_Clear this file after each run. Jarvis archives completed tasks to jarvis/tasks/_
```

---

## 7. Model Routing Strategy

| Task Type | Model | Why |
|---|---|---|
| Orchestration, complex reasoning | Claude Sonnet 4.6 (Enterprise) | Reasoning depth needed |
| Classification, routing, summaries | Claude Haiku 4.5 (Enterprise) | Fast, cheap, sufficient |
| Document/email tasks | Microsoft Copilot (manual) | M365 license, $0 marginal cost |
| Code assistance | Continue.dev + LiteLLM | Existing workflow, don't disrupt |
| Heavy architecture questions | Claude Opus 4.8 (Enterprise) | Use sparingly, V2 only |

**Never route Jarvis through LiteLLM.** LiteLLM is reserved for Continue.dev coding workflows. Jarvis uses Claude Enterprise API directly — separate billing, doesn't touch your $25 budget.

---

## 8. Infrastructure

### GitHub Actions Workflow (MVP)
```
.github/
  workflows/
    jarvis.yml    ← triggered on commit to jarvis/inbox.md
                  ← also runs on cron schedule (e.g., nightly 11pm)
```

### Power Automate Flow
- **Trigger**: HTTP webhook POST from GitHub Actions job completion
- **Action**: Write file to SharePoint document library (vault location)
- **Output file**: `jarvis/digests/[date].md`
- **No premium connectors required** — SharePoint + HTTP are standard

### Secrets (GitHub Actions)
- `ANTHROPIC_API_KEY` — Claude Enterprise API key
- `POWER_AUTOMATE_WEBHOOK_URL` — your PA flow webhook URL
- `GCLOUD_AUTH` — deferred until service account provisioned

---

## 9. Security & Compliance Model

| Rule | Implementation |
|---|---|
| No PII handling | Agent prompt includes hard stop: never store names, emails, customer data |
| No production writes | All GCP access read-only. Agent has no write credentials |
| Human-in-the-loop for external sends | All emails/Teams messages written as drafts only, flagged `[HUMAN APPROVAL REQUIRED]` |
| No unapproved SaaS | Claude Enterprise API + GitHub + Power Automate + SharePoint only |
| Audit trail | Every task logged to `jarvis/tasks/` with timestamp and model used |
| Token logging | Each agent logs `{agent, model, input_tokens, output_tokens, task_id}` to task file |

---

## 10. Suggested Repo Structure

```
jarvis/
  README.md
  jarvis.yml                  ← GitHub Actions workflow
  orchestrator/
    main.py                   ← entry point, reads inbox.md
    agents/
      orchestrator.py
      research.py
      gcp_discovery.py
      obsidian_writer.py
    utils/
      token_logger.py
      vault_reader.py
      power_automate.py       ← webhook POST to PA
  prompts/
    orchestrator.md
    research.md
    gcp_discovery.md
    obsidian_writer.md
  config/
    settings.yaml             ← model routing, agent settings
  tests/
    test_orchestrator.py
    test_gcp_discovery.py
```

---

## 11. Token Usage & Cost Controls

- Log per-agent token usage to each task file
- Weekly digest includes: total tokens used, cost estimate per workflow, most expensive agents
- Prompt compression: Research Agent reads only the relevant section of a vault note, not the full file
- Context pruning: Orchestrator passes only the task + top 3 relevant knowledge notes to each subagent
- Caching: Evergreen vault notes serve as a prompt cache — if the answer is in the vault, skip the API call

---

## 12. Parallel Actions — Start Now

| Action | Owner | Why now |
|---|---|---|
| Email IT partner: who owns GCP IAM? | You | Start approval clock this week |
| Request service account: `bigquery.dataViewer` + `bigquery.jobUser` (non-prod only) | You | 4-8 week approval process |
| Create GitHub Actions workflow skeleton | Jarvis/Codex | Unblocks all overnight automation |
| Create Power Automate webhook flow | You | 30-min setup, unblocks output pipeline |
| Initialize `jarvis/` folder in Obsidian vault | You | Required before first run |

---

## 13. V2 Roadmap (Do Not Build in MVP)

| Feature | Unlocked by |
|---|---|
| GCP Agent overnight runs | Service account approved |
| PR Review Agent | Stable orchestrator + validation baseline |
| Ad Hoc Request Intake (Outlook/Teams) | Power Automate + HTTP endpoint working |
| Validation Agent | 2-3 completed MVP workflows to baseline against |
| Copilot Studio delegation | Map which tasks you're manually handing off most |
| Migrate compute to GCP/Azure | Service account + infra request approved |
| Programmatic Copilot routing | Copilot Studio + Power Automate flow built |

---

## 14. Open Questions / Risks

| Question | Risk if unresolved |
|---|---|
| GCP IAM owner unknown | GCP Agent stays daytime-only indefinitely |
| SharePoint vault path for Power Automate | Output pipeline blocked |
| Claude Enterprise API key accessible outside VPN? | GitHub Actions runner may not reach it |
| Copilot API access level | Limits V2 programmatic routing |
