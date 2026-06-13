# Contract: Task Result JSON Schema

**Version**: 1.0
**Owner**: Orchestrator Agent (produces) / Obsidian Agent (consumes)

---

## Purpose

The TaskResult is the primary data structure passed between agents and persisted to the vault. It is the source of truth for what happened during a task run.

---

## JSON Schema

```json
{
  "task_id": "task-001-gcp-discovery",
  "task_title": "GCP dataset discovery for Aprilia project",
  "run_timestamp": "2026-06-14T02:31:00Z",
  "mode": "overnight",
  "status": "completed",
  "agents_executed": [
    {
      "agent_name": "orchestrator",
      "model": "claude-sonnet-4-6",
      "input_tokens": 1200,
      "output_tokens": 450,
      "duration_seconds": 4.2,
      "output": {
        "plan": "Route to GCP agent, then Obsidian agent",
        "knowledge_context_used": ["jarvis/knowledge/gcp/datasets.md"]
      },
      "errors": []
    },
    {
      "agent_name": "gcp_discovery",
      "model": "claude-haiku-4-5",
      "input_tokens": 800,
      "output_tokens": 600,
      "duration_seconds": 6.1,
      "output": {
        "datasets_found": ["aprilia_prod", "aprilia_staging"],
        "tables": [
          {"dataset": "aprilia_prod", "table": "orders", "description": "Customer order records"},
          {"dataset": "aprilia_prod", "table": "inventory", "description": "Parts inventory"}
        ],
        "plain_english_summary": "Found 2 datasets and 4 tables related to Aprilia..."
      },
      "errors": []
    },
    {
      "agent_name": "obsidian",
      "model": "claude-haiku-4-5",
      "input_tokens": 1800,
      "output_tokens": 900,
      "duration_seconds": 8.3,
      "output": {
        "notes_updated": ["jarvis/knowledge/gcp/datasets.md"],
        "task_file_written": "jarvis/tasks/task-001-gcp-discovery.md",
        "digest_updated": "jarvis/digests/2026-06-14.md"
      },
      "errors": []
    }
  ],
  "output_summary": "Found 4 BigQuery tables in 2 Aprilia datasets. Evergreen GCP note updated.",
  "draft_communications": [],
  "clarifications_needed": [],
  "knowledge_updates": [
    "jarvis/knowledge/gcp/datasets.md",
    "jarvis/tasks/task-001-gcp-discovery.md"
  ]
}
```

---

## Field Rules

| Field | Rule |
|-------|------|
| `task_id` | Format: `task-NNN-<slug>`. NNN is zero-padded sequential integer. |
| `status` | `completed` if all agents ran without fatal errors; `partial` if some agents errored; `needs_clarification` if Orchestrator could not determine what to do |
| `draft_communications` | Empty list if no drafts produced. Items must have `flag: "[HUMAN APPROVAL REQUIRED]"` |
| `clarifications_needed` | Plain-language questions for the operator; written to digest verbatim |
| `errors` (per agent) | Empty list if no errors. Non-empty errors do not automatically fail the run; Orchestrator decides if fatal |

---

## Vault Markdown Format (persisted task record)

When the Obsidian Agent writes the task to `jarvis/tasks/task-NNN-<slug>.md`, it uses this structure:

```markdown
# Task: {task_title}

**Task ID**: task-001-gcp-discovery
**Run**: 2026-06-14T02:31:00Z
**Mode**: overnight
**Status**: completed

## Request

{original request from inbox.md}

## Output

{output_summary}

## Token Usage

| Agent | Model | Input | Output | Duration |
|-------|-------|-------|--------|----------|
| orchestrator | claude-sonnet-4-6 | 1200 | 450 | 4.2s |
| gcp_discovery | claude-haiku-4-5 | 800 | 600 | 6.1s |
| obsidian | claude-haiku-4-5 | 1800 | 900 | 8.3s |
| **Total** | | **3800** | **1950** | **18.6s** |

**Estimated cost**: $0.09

## Knowledge Updates

- [[gcp-datasets]] — updated with Aprilia tables

## Draft Communications

_(none)_
```
