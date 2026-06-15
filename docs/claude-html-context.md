# Claude HTML Context for Jarvis

## Overview

Jarvis is an internal task-orchestration MVP. It accepts tasks from a markdown inbox or a direct CLI task, runs deterministic Python "agents", and writes markdown output intended for an Obsidian vault through Power Automate, SharePoint, and OneDrive.

Preserve these labels in the HTML: `[Confirmed]`, `[Inferred]`, `[Unverified]`, and `[Contradictory Evidence]`.

## What the Repository Appears to Be

- [Confirmed] A Python 3.12 workflow project with GitHub Actions as the scheduled/manual runtime.
- [Confirmed] Operator task input is `jarvis/inbox.md`.
- [Confirmed] Daytime GCP discovery can also be run locally with `python orchestrator/main.py --task "..."`.
- [Confirmed] Output is a batch of markdown files posted to Power Automate.
- [Confirmed] The task runtime is deterministic and does not use Anthropic for task execution, but GitHub Actions now performs a real Anthropic smoke test before running Jarvis.
- [Inferred] The repo is a validated MVP scaffold for safe automation, with real Claude reasoning deferred.

Evidence: `orchestrator/main.py`, `.github/workflows/jarvis.yml`, `orchestrator/agents/*.py`, `requirements.txt`, `prompts/*.md`.

## What Is Implemented vs Incomplete

### Implemented

- Inbox parser with validation and cleared-template no-task behavior.
- Deterministic orchestration and routing.
- Local vault keyword search and research cache-hit flag.
- Context cap through `research.max_tokens_per_note`.
- Obsidian task record generation.
- Daily digest generation.
- Weekly cost rollup from recent task files plus persisted `jarvis/usage-history.json`.
- Lesson file and knowledge update payload generation.
- Draft communication staging with `[HUMAN APPROVAL REQUIRED]`.
- Power Automate webhook client with retry and `jarvis/run-errors.log`.
- Daytime GCP discovery using local `bq` metadata commands.
- Overnight GCP skip guard.
- Configurable PII modes: `strict`, `standard`, `off`.
- Unit tests covering Phase 4-6 behaviors.

### Incomplete or Stubbed

- No real Anthropic API calls.
- Prompt files are not loaded at runtime.
- Model names are audit labels only.
- Token counts are zero until real model usage exists.
- Configured timeout values are not enforced.
- Power Automate flow is external and not version-controlled.
- Unique task IDs are not implemented; IDs start with `task-001-`.
- GitHub Actions does not run unit tests.
- Phase 2 ecosystem agents are planned but not implemented.

## Repository Snapshot

- Entry point: `orchestrator/main.py`
- Agents: `orchestrator/agents/orchestrator.py`, `research.py`, `gcp_discovery.py`, `obsidian_writer.py`
- Utilities: `orchestrator/utils/inbox_parser.py`, `power_automate.py`, `pii_guard.py`, `token_logger.py`, `vault_reader.py`
- Config: `config/settings.yaml`
- Workflow: `.github/workflows/jarvis.yml`
- Input: `jarvis/inbox.md`
- Specs: `specs/001-jarvis-mvp/`
- Future planning: `specs/002-jarvis-phase2/`, `specs/003-phase2-agent-ecosystem/`
- Tests: `tests/`
- Validation evidence: `specs/001-jarvis-mvp/Verifcation-evidence/`
- Persisted weekly rollup state: `jarvis/usage-history.json`

Current regression baseline:

- `Ran 50 tests ... OK`

## Architecture Summary

Data flow:

1. Operator edits `jarvis/inbox.md` or runs `main.py --task`.
2. `orchestrator/main.py` loads `config/settings.yaml`.
3. Inbox parser returns a task or no-task state.
4. Vault reader finds relevant local markdown notes.
5. Orchestrator builds a `TaskResult`.
6. Research runs if requested.
7. GCP discovery runs if requested and task mode is daytime.
8. Obsidian writer renders task, digest, lesson, and knowledge markdown payloads.
9. Power Automate writes payloads to SharePoint.
10. GitHub Actions clears and commits inbox only after successful post.

Important boundary: Power Automate is production-critical but not stored as code in this repo.

## Likely Build and Run Flow

Local setup:

```powershell
python -m pip install -r requirements.txt
$env:PYTHONDONTWRITEBYTECODE='1'
python -m unittest discover -s tests
python orchestrator/main.py --dry-run
```

Local daytime GCP:

```powershell
$env:POWER_AUTOMATE_WEBHOOK_URL=''
python orchestrator/main.py --task "List all BigQuery datasets in the non-prod environment"
```

GitHub Actions secrets:

- `ANTHROPIC_API_KEY`
- `POWER_AUTOMATE_WEBHOOK_URL`

Workflow schedule:

- [Confirmed] Current cron is `0 23 * * 1-5`.

## Key Decisions and Tradeoffs

- Inbox-as-input keeps intake simple and auditable.
- Vault-as-output enforces no auto-send behavior.
- Sequential Python functions reduce MVP complexity but do not provide true agent reasoning.
- Power Automate avoids direct Graph/SharePoint auth in Python, but moves critical behavior outside source control.
- GCP discovery uses local operator auth while service-account automation is deferred.
- PII handling is configurable, which improves practical usability but requires stricter run discipline.

## Risks, Gaps, and Unknowns

- [Confirmed] `pii.mode` is currently `off` in `config/settings.yaml`; use `strict` for sensitive runs.
- [Confirmed] Phase 6 evidence is current for weekly rollup, context pruning, and research `cache_hit`.
- [Confirmed] Unit tests are not run in GitHub Actions.
- [Confirmed] Power Automate smoke test writes `jarvis/test.md` on normal runs.
- [Confirmed] Task IDs can collide.
- [Confirmed] Real Anthropic task execution is absent even though the workflow smoke test is real.
- [Confirmed] Timeout settings are not enforced.
- [Unverified] Live Power Automate upsert behavior.
- [Unverified] OneDrive sync reliability.
- [Unverified] Anthropic model/API validity.

## Errors and Lessons Learned

- Wrong Power Automate URL produced `DirectApiAuthorizationRequired`.
- Parse JSON failed when the flow parsed the wrong trigger content.
- SharePoint path handling initially flattened or misplaced vault paths.
- Draft requests initially produced no draft body.
- PII strict behavior initially missed name-like text.
- Cleared inbox template initially became a fake task.
- Python bytecode files appeared in git status during tests.
- `bq ls --project` failed; `--project_id` was required.
- Python could not find `bq` until Windows shim resolution was added.
- Per-table schema failures and empty table-list output had to degrade locally rather than fail the whole GCP run.
- `pii.mode: off` evidence showed remaining redaction markers until sanitizer paths were corrected.
- Rejected pushes repeatedly occurred because GitHub Actions wrote back cleared inbox state and `jarvis/usage-history.json` to `main`.
- `git rebase --continue` can fail if `code --wait` is broken; `$env:GIT_EDITOR='true'` is a working recovery.
- Detached `HEAD` and `rebase-merge` states were caused by committing during an active rebase.

## Recommended Stabilization Steps

1. Add unit tests to GitHub Actions.
2. Rerun Scenario 4 and capture clean `pii.mode: off` evidence.
3. Decide whether committed `pii.mode: off` is acceptable or should be changed to `strict`.
4. Export or fully document the Power Automate flow.
5. Implement unique task IDs.
6. Add workflow concurrency.
7. Move smoke testing out of normal production runs.
8. Design the Anthropic client boundary before adding model calls.
9. Publish a short operator git recovery runbook for workflow-bot conflicts.

## Known Git Failure Recovery

```powershell
git status --short --branch
git fetch origin
$env:GIT_EDITOR='true'
git pull --rebase origin main
```

If `jarvis/inbox.md` conflicts:

```powershell
git add jarvis/inbox.md
git rebase --continue
git push origin main
```

If the rebase state is already broken:

```powershell
git rebase --abort
git fetch origin
$env:GIT_EDITOR='true'
git pull --rebase origin main
git push origin main
```

## Recommended Next Improvements

1. Create an operator README for daily use and troubleshooting.
2. Add a validation status matrix for Phase 4-6 evidence.
3. Centralize inbox template text.
4. Add stronger PII fixtures and mode-specific validation commands.
5. Add a GCP preflight command that checks `bq` availability, auth, and project visibility.
6. Clarify whether `specs/002-*` and `specs/003-*` are active backlog.
7. Implement real token capture when Anthropic calls are introduced.
