# Jarvis Phase 2 — Feature Specification

**Feature ID**: 002-jarvis-phase2  
**Status**: Draft  
**Created**: 2026-06-14  
**Depends on**: 001-jarvis-mvp (must be complete and stable)

---

## Overview

Phase 2 expands the Jarvis MVP into a scalable, observable, and continuously improving agent ecosystem. It adds four new agents, a structured logging layer, a prompt library system, and a governance-safe CI recommendation engine.

Phase 2 DOES NOT replace Phase 1. All existing agents, contracts, and integrations are extended, not rewritten.

---

## Goals

1. **Observability** — Every agent run produces structured, queryable JSON logs. No more Markdown-only audit trail.
2. **Quality gates** — A Validation Agent scores every agent output before it is committed to the TaskResult. Bad outputs are retried or skipped, never silently passed through.
3. **Continuous improvement** — A CI Agent analyzes logs bi-weekly and produces human-reviewable recommendations for prompt, routing, and config improvements. No auto-deployment.
4. **Vault health** — A Vault Maintenance Agent keeps the Obsidian vault organized with auto-fixes for low-risk issues and human-approval proposals for high-risk ones.
5. **PR reviews** — A PR Review Agent handles on-demand pull request analysis via inbox task, writing structured reviews to the vault only.

---

## Key Constraints (Inherited from Phase 1 — Do Not Relax)

- **No PII**: All agent outputs pass through `pii_guard`. Hard stop.
- **No auto-send**: Draft communications go to vault with `[HUMAN APPROVAL REQUIRED]`. No exceptions.
- **No auto-deploy CI changes**: CI Agent produces recommendations only. Human approves via inbox task.
- **Read-only GCP**: GCP agent uses `bq ls` and `bq show` only.
- **Approved services only**: `anthropic`, `google-cloud-bigquery`, `requests`, `pyyaml`. PR Review Agent adds GitHub API calls via `requests` (already approved).
- **No GitHub writes**: `GITHUB_TOKEN` must be read-only (`repo:read`). PR Review Agent never posts to GitHub.

---

## New Agents

| Agent | Model | Trigger | Output |
|---|---|---|---|
| Validation Agent | claude-haiku-4-5 | Inline, after every agent | ValidationResult dict; confidence score |
| CI Agent | claude-sonnet-4-6 | Bi-weekly cron (Sun + Wed 11PM) | `jarvis/ci/ci_report_{date}.md` |
| Vault Maintenance Agent | claude-haiku-4-5 | Weekly cron (Sat 10PM) | Auto-fixes + `jarvis/vault/maintenance_{date}.md` |
| PR Review Agent | claude-sonnet-4-6 | Inbox task (`agents: pr_review`) | `jarvis/tasks/{task_id}.md` |

---

## New Storage

| Path | Purpose | Format |
|---|---|---|
| `jarvis/logs/{date}/{run_id}.json` | Structured agent execution logs | JSON array |
| `jarvis/ci/ci_report_{date}.md` | CI Agent human-readable report | Markdown |
| `jarvis/ci/ci_scores_{date}.json` | CI scoring data for next cycle | JSON |
| `jarvis/vault/maintenance_{date}.md` | Vault Maintenance proposals | Markdown |
| `prompts/library.json` | Prompt metadata index | JSON |
| `prompts/versions/` | Archived prompt versions | Markdown |

---

## Confidence Thresholds

| Score | Action |
|---|---|
| ≥ 0.90 | Accept output, continue pipeline |
| 0.60–0.89 | Retry agent once; accept if retry score ≥ 0.60 |
| < 0.60 | Skip agent, mark `partial`, add to digest as `[HUMAN REVIEW REQUIRED]` |

Thresholds are self-calibrating over time: when 20+ data points exist for an agent, the CI Agent evaluates whether thresholds should shift and proposes adjustment in the next bi-weekly report.

---

## pm_workflow Integration

`pm_workflow` is a set of PowerShell scripts that write classified email briefs to SharePoint under `PM/`. Phase 2 integration: Jarvis writes its outputs to the same SharePoint library under `Jarvis/`. No changes to pm_workflow. Phase 3+ will absorb pm_workflow logic into a dedicated Email Classification Agent.

---

## Build Sequence

1. **Sprint 1** (Weeks 1–2): Structured JSON logging — `run_logger.py`, `run_id`/`trace_id`, webhook payload update
2. **Sprint 2** (Weeks 3–4): Validation Agent — quality gates, retry/skip logic, confidence scores in logs
3. **Sprint 3** (Weeks 5–7): CI Agent + Prompt Library — bi-weekly analysis, `library.json`, inbox approval flow
4. **Sprint 4** (Weeks 8–9): Vault Maintenance Agent — auto-fix + proposal reports
5. **Sprint 5** (Weeks 10–11): PR Review Agent — GitHub API integration, inbox task trigger

---

## Implementation Detail

See [plan.md](plan.md) for the full architecture, agent designs, log schema, CI scoring model, orchestration decision tree, and risk register.
