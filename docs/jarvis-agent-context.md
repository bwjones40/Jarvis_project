# Jarvis Future Agent Context

## 1. What Jarvis Appears to Be

[Confirmed] Jarvis is a Python/GitHub Actions workflow for operator-assigned task execution. The input is `jarvis/inbox.md`; the output is markdown files sent through Power Automate to a SharePoint-backed Obsidian vault. Evidence: `specs/001-jarvis-mvp/spec.md`, `orchestrator/main.py`, `.github/workflows/jarvis.yml`.

[Inferred] The intended end-state is an internal overnight AI command center. The current implementation is a deterministic MVP skeleton that validates plumbing, safety gates, and vault output shape before real Claude reasoning is added.

## 2. Current Confidence Map

| Topic | Status | Confidence | Evidence |
|---|---|---:|---|
| Inbox parsing | Implemented, with template no-task sentinel | High | `orchestrator/utils/inbox_parser.py` |
| GitHub workflow | Implemented, currently in temporary cron mode | High | `.github/workflows/jarvis.yml` |
| Power Automate posting | Implemented in Python, external flow unversioned | High | `orchestrator/utils/power_automate.py` |
| Task/digest markdown | Implemented | High | `orchestrator/agents/obsidian_writer.py` |
| Draft staging | Implemented for simple Teams/email cases | High | `tests/test_obsidian_writer.py` |
| PII redaction | Partial regex implementation | High | `orchestrator/utils/pii_guard.py` |
| Real Anthropic agent calls | Not implemented | High | no source usage of Anthropic client |
| GCP discovery | Not implemented | High | missing `gcp_discovery.py` |
| Create/update SharePoint behavior | External and unverified in repo | Medium | webhook contract and user validation |
| Weekly cost rollup | Not implemented | High | `tasks.md`, no code path |

## 3. What Is Stable vs Uncertain

### Stable

- [Confirmed] `python -m unittest discover -s tests` is the current local test command.
- [Confirmed] `python orchestrator/main.py --dry-run` parses an active inbox or prints `No task in inbox`.
- [Confirmed] No-task digest generation exists when `parse_inbox()` returns `None`.
- [Confirmed] The code has no email/Teams send API calls.

### Uncertain

- [Unverified] Current Power Automate create/update behavior.
- [Unverified] Whether Section 6 scheduled validation passed after the template fix.
- [Unverified] Whether all generated files are landing in the correct Obsidian folders after PA flow edits.
- [Unverified] Whether the cron has been restored to nightly.

## 4. Critical Files and Why They Matter

- `orchestrator/main.py`: runtime entry point and branch point between no-task and task execution.
- `orchestrator/utils/inbox_parser.py`: parser boundary; bugs here can create fake tasks or reject valid tasks.
- `orchestrator/agents/orchestrator.py`: creates `TaskResult` and routing. Currently deterministic.
- `orchestrator/agents/research.py`: local vault search and research AgentRun generation.
- `orchestrator/agents/obsidian_writer.py`: task/digest/lesson markdown generation and draft staging.
- `orchestrator/utils/pii_guard.py`: compliance-sensitive sanitization helper.
- `orchestrator/utils/power_automate.py`: webhook payload sender and retry behavior.
- `.github/workflows/jarvis.yml`: live runtime configuration, schedule, secrets, bot commit behavior, smoke test.
- `config/settings.yaml`: intended config surface; not all fields are active.
- `specs/001-jarvis-mvp/`: intended product and contract sources.
- `docs/jarvis-mvp-verification-guide.md`: current operator validation guide.

## 5. Dangerous Areas / Change Risks

- [Confirmed] Changing `jarvis/inbox.md` triggers GitHub Actions on push.
- [Confirmed] Changing `.github/workflows/jarvis.yml` can alter live automation and scheduled run frequency.
- [Confirmed] Touching `pii_guard.py` can create compliance regressions.
- [Confirmed] Touching `obsidian_writer.py` can change vault file paths, task records, digest content, and draft safety behavior.
- [Inferred] Changing Power Automate expressions outside source control can silently break production output while tests still pass.
- [Confirmed] The workflow commits back to `main`; local changes must be rebased after bot commits.

## 6. What to Validate First

1. `git status --short` is clean before any new work.
2. `.github/workflows/jarvis.yml` cron is either intentionally temporary or restored to `0 23 * * 1-5`.
3. `python -m unittest discover -s tests` passes locally.
4. `python orchestrator/main.py --dry-run` prints `No task in inbox` for the cleared template.
5. Power Automate writes nested `jarvis/tasks`, `jarvis/digests`, and `jarvis/agents` paths correctly.
6. A PII validation task does not write names or emails into vault outputs.

## 7. Safe Starting Points for Improvement

- Add CI test execution to `.github/workflows/jarvis.yml`.
- Export or document the Power Automate flow in repo docs.
- Implement create-or-update/upsert behavior in Power Automate.
- Replace fixed `task-001-` task IDs.
- Centralize the inbox template string to avoid drift between parser tests and `main.py`.
- Add richer PII test fixtures before enabling real LLM calls.

## 8. Recommended Continuous Improvement Backlog

1. Restore cron schedule from validation mode.
2. Add a validation status table to docs for Sections 1-6.
3. Implement Power Automate create-or-update behavior.
4. Add unique task ID allocation.
5. Add GitHub Actions unit-test step.
6. Remove or gate the smoke test so it does not run on every production task.
7. Implement real Anthropic API calls with prompt loading and token capture.
8. Add GCP discovery only after read-only command/test boundaries are in place.
9. Add weekly cost rollups after token counts are real.

## 9. What a New Agent Should Read First

1. `AGENTS.md`
2. `specs/001-jarvis-mvp/spec.md`
3. `specs/001-jarvis-mvp/plan.md`
4. `specs/001-jarvis-mvp/contracts/inbox-schema.md`
5. `specs/001-jarvis-mvp/contracts/task-result-schema.md`
6. `specs/001-jarvis-mvp/contracts/webhook-payload.md`
7. `orchestrator/main.py`
8. `orchestrator/utils/inbox_parser.py`
9. `orchestrator/agents/obsidian_writer.py`
10. `.github/workflows/jarvis.yml`
11. `docs/jarvis-mvp-verification-guide.md`
12. `docs/jarvis-learning-log.md`
