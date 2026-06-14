# Claude HTML Context for Jarvis

## Overview

Jarvis is an internal task-orchestration MVP intended to run assigned tasks overnight and deliver markdown results to an Obsidian vault through GitHub Actions, Power Automate, SharePoint, and OneDrive sync.

Use this document to build a clean human-readable HTML summary. Preserve uncertainty labels: `[Confirmed]`, `[Inferred]`, `[Unverified]`, and `[Contradictory Evidence]`.

## What the Repository Appears to Be

- [Confirmed] A Python 3.12 workflow project with GitHub Actions as the runtime.
- [Confirmed] The operator assigns work by editing and pushing `jarvis/inbox.md`.
- [Confirmed] The runtime posts generated markdown files to a Power Automate webhook.
- [Inferred] The current code is an MVP scaffold and safety/integration validation layer, not yet a full Claude-powered agent system.

Evidence: `orchestrator/main.py`, `.github/workflows/jarvis.yml`, `specs/001-jarvis-mvp/spec.md`.

## What Is Implemented vs Incomplete

### Implemented

- Inbox parser with validation and cleared-template no-task behavior.
- Deterministic orchestrator routing and TaskResult creation.
- Local vault keyword search.
- Markdown task record and digest generation.
- Basic lesson file payload generation.
- Draft staging with `[HUMAN APPROVAL REQUIRED]`.
- Regex-based email/name redaction.
- Power Automate webhook client with retries.
- GitHub Actions workflow with push/schedule/manual triggers.
- Unit tests for parser, orchestrator, obsidian writer, token logger, and Power Automate client.

### Incomplete or Stubbed

- No Anthropic API calls are made despite dependency and prompt files.
- Prompt files are not loaded by runtime code.
- GCP discovery is planned but absent.
- Task IDs always use `task-001-`.
- Weekly cost rollup is not implemented.
- Token counts are zero because there are no model calls.
- Power Automate flow is external and not version-controlled.
- Create-or-update semantics are not guaranteed by repo code.

## Repository Snapshot

- Entry point: `orchestrator/main.py`
- Main agents: `orchestrator/agents/orchestrator.py`, `orchestrator/agents/research.py`, `orchestrator/agents/obsidian_writer.py`
- Utilities: `orchestrator/utils/*.py`
- Config: `config/settings.yaml`
- Workflow: `.github/workflows/jarvis.yml`
- Input file: `jarvis/inbox.md`
- Specs: `specs/001-jarvis-mvp/`
- Tests: `tests/`
- Validation guide: `docs/jarvis-mvp-verification-guide.md`

## Architecture Summary

Data flow:

1. Operator edits `jarvis/inbox.md`.
2. GitHub Actions runs on push, manual dispatch, or schedule.
3. `orchestrator/main.py` parses inbox.
4. If no task, it builds a no-task digest.
5. If task exists, deterministic agent functions build a `TaskResult`.
6. Obsidian writer renders markdown payloads.
7. Power Automate writes files into SharePoint.
8. OneDrive sync exposes files to Obsidian.
9. GitHub Actions commits cleared inbox back to `main`.

Important boundary: Power Automate is critical but not represented as code in this repo.

## Likely Build and Run Flow

Local setup:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests
python orchestrator/main.py --dry-run
```

GitHub Actions secrets:

- `ANTHROPIC_API_KEY`
- `POWER_AUTOMATE_WEBHOOK_URL`

Current schedule:

- [Confirmed] `.github/workflows/jarvis.yml` currently has `*/5 * * * *`.
- [Inferred] This is a temporary validation schedule and should be restored to `0 23 * * 1-5`.

## Key Decisions and Tradeoffs

- Inbox file is the only input interface for MVP. This reduces auth and intake complexity.
- Vault markdown is the only output interface. This enforces no auto-send behavior.
- Sequential Python functions are used instead of async or queues. This simplifies the MVP.
- Power Automate/SharePoint handles vault writes. This avoids direct Graph auth from GitHub Actions but moves key behavior outside source control.
- Current PII guard is code-based but heuristic.

## Risks, Gaps, and Unknowns

- Temporary cron may still be active.
- Task ID collisions are likely.
- Power Automate upsert behavior is not codified in repo.
- Smoke test writes extra `jarvis/test.md` artifacts.
- No real Anthropic calls yet.
- PII redaction is not comprehensive.
- GCP discovery is not built.
- Unit tests are not run in GitHub Actions yet.
- The live Power Automate flow needs exported documentation.

## Errors and Lessons Learned

- Wrong Power Automate URL produced OAuth-required errors.
- Parse JSON step failed because the trigger body schema already exposed fields.
- Hardcoded SharePoint folder mapping wrote files outside intended subfolders.
- Draft communications initially stayed empty until request-driven draft staging was added.
- PII name redaction initially failed until name-like regex redaction was added.
- Cleared inbox template initially created fake tasks until parser sentinel logic was added.
- Git pushes can be rejected because the workflow commits inbox-clearing changes back to `main`.
- Python bytecode files were once tracked and had to be removed from Git tracking.

## Recommended Stabilization Steps

1. Restore the cron schedule.
2. Export or document the exact Power Automate flow.
3. Implement create-or-update behavior for SharePoint files.
4. Add unique task IDs.
5. Add unit tests to GitHub Actions.
6. Decide whether the smoke test should run every task or only on demand.
7. Expand PII tests before enabling real model calls.

## Recommended Next Improvements

1. Centralize the inbox template string.
2. Make `run_metadata` accurate in `orchestrator/main.py`.
3. Add Anthropic client wrapper with retries and token logging.
4. Load prompt files explicitly.
5. Implement GCP discovery only after read-only subprocess tests exist.
6. Add weekly cost rollup after token usage becomes nonzero.
7. Create `jarvis/README.md` for operator workflow and troubleshooting.
