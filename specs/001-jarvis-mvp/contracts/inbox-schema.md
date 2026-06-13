# Contract: Inbox File Format (`jarvis/inbox.md`)

**Version**: 1.0
**Owner**: Operator (writes) / Orchestrator Agent (reads)

---

## Purpose

The inbox file is the sole interface between the operator and Jarvis. It must be parseable by the Orchestrator without ambiguity.

---

## Schema

```markdown
# Jarvis Inbox

## Task: {title}
**Priority**: high | medium | low
**Mode**: overnight | daytime
**Agents needed**: orchestrator[, research][, gcp][, obsidian]
**Due**: {YYYY-MM-DD} | next run

### Request
{Plain-language description. May be multi-paragraph. Required.}

### Context
{Optional. Project name, who asked, SharePoint doc links.}

### Copilot handoff
{Optional. What should be manually handed to Copilot and why.}

---
_Clear this file after each run. Jarvis archives completed tasks to jarvis/tasks/_
```

---

## Parsing Rules

| Rule | Behavior |
|------|----------|
| Title extraction | Text after `## Task:` on the same line |
| Field parsing | `**FieldName**: value` — case-insensitive field names |
| Agents list | Comma-separated values; `orchestrator` always assumed even if omitted |
| Section content | Text under each `### Heading` until next `###` or `---` |
| Empty file | Orchestrator skips execution; writes "No task in inbox" to digest |
| Multiple tasks | Not supported in MVP; Orchestrator uses the first task found and warns |

---

## Validation Errors (Orchestrator rejects and writes error to digest)

- `Priority` not one of `high`, `medium`, `low`
- `Mode` not one of `overnight`, `daytime`
- `Request` section empty or missing
- File contains no `## Task:` heading

---

## Example (valid)

```markdown
# Jarvis Inbox

## Task: GCP dataset discovery for Aprilia project
**Priority**: high
**Mode**: daytime
**Agents needed**: orchestrator, gcp, obsidian
**Due**: 2026-06-14

### Request
Find all BigQuery tables related to the Aprilia project. Aprilia is a motorcycle manufacturer.
I need to know what tables exist, what they contain at a high level, and which dataset they live in.

### Context
Aprilia team asked in a Teams message. Project code: APR-2024.

---
_Clear this file after each run. Jarvis archives completed tasks to jarvis/tasks/_
```
