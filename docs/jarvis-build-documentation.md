# Jarvis Build Documentation

## 1. Project Overview

[Confirmed] Jarvis is intended to be an internal AI orchestration system that accepts operator tasks from `jarvis/inbox.md`, runs an overnight/sequential agent pipeline, and writes task results plus a daily digest into an Obsidian vault through Power Automate, SharePoint, and OneDrive sync. Evidence: `specs/001-jarvis-mvp/spec.md`, `AGENTS.md`, `jarvis-mvp-plan.md`.

[Confirmed] The repository currently implements a small Python workflow, not a fully autonomous Claude-backed agent system. The implemented runtime is deterministic Python code in `orchestrator/main.py`, `orchestrator/agents/*.py`, and `orchestrator/utils/*.py`. Evidence: `orchestrator/main.py`, `orchestrator/agents/orchestrator.py`, `orchestrator/agents/research.py`, `orchestrator/agents/obsidian_writer.py`.

[Inferred] The current practical MVP is closer to a workflow skeleton and validation harness than a production AI system. It parses tasks, builds structured task records, posts markdown payloads to Power Automate, stages simple draft communications, and protects against some PII patterns. It does not yet call the Anthropic SDK for task reasoning.

## 2. Repository Forensics Summary

[Confirmed] The repo is spec-first. The most complete product definition lives under `specs/001-jarvis-mvp/`, especially `spec.md`, `plan.md`, `data-model.md`, and `contracts/`. Source code is smaller and implements only a subset of the intended plan.

[Confirmed] CI/CD is through `.github/workflows/jarvis.yml`. It runs on `jarvis/inbox.md` pushes, a cron schedule, and manual dispatch. It installs Python 3.12, checks that `ANTHROPIC_API_KEY` exists and resolves `api.anthropic.com`, runs `python orchestrator/main.py`, commits a cleared inbox when changed, and sends a Power Automate smoke-test payload.

[Confirmed] The current workflow cron is temporarily set to `*/5 * * * *`, not the intended nightly `0 23 * * 1-5`. Evidence: `.github/workflows/jarvis.yml`. This is a temporary validation state and should be restored after Section 6 validation.

[Contradictory Evidence] `specs/001-jarvis-mvp/tasks.md` lists many tasks as unchecked even when code exists. Treat that file as a planned task inventory, not a current progress tracker. Evidence: `tests/test_inbox_parser.py`, `orchestrator/utils/inbox_parser.py`, `tests/test_obsidian_writer.py`.

## 3. Repository Map

| Area | Purpose | Maturity | Confidence | Evidence |
|---|---|---:|---:|---|
| `orchestrator/main.py` | CLI and workflow entry point. Loads settings, parses inbox, routes through orchestrator/research/obsidian, posts outputs, clears inbox after successful post. | Partial | High | `orchestrator/main.py` |
| `orchestrator/agents/orchestrator.py` | Builds a `TaskResult` skeleton, routes requested agents, flags clarification/PII. | Partial | High | `orchestrator/agents/orchestrator.py` |
| `orchestrator/agents/research.py` | Performs local vault keyword search and records context summary. | Partial | High | `orchestrator/agents/research.py` |
| `orchestrator/agents/obsidian_writer.py` | Builds task markdown, digest markdown, lesson payloads, and simple draft communications. | Partial | High | `orchestrator/agents/obsidian_writer.py` |
| `orchestrator/utils/inbox_parser.py` | Parses the markdown inbox contract and treats the cleared template as no task. | Implemented for MVP | High | `tests/test_inbox_parser.py` |
| `orchestrator/utils/power_automate.py` | Sends webhook payloads with retries and logs failures to `jarvis/run-errors.log`. | Implemented but minimal | High | `tests/test_power_automate.py` |
| `orchestrator/utils/vault_reader.py` | Reads and searches local markdown notes by filename, H1, and content keyword match. | Minimal | High | `orchestrator/utils/vault_reader.py` |
| `orchestrator/utils/pii_guard.py` | Regex-based email/name redaction with a small allowlist. | Fragile partial | High | `tests/test_orchestrator.py`, `tests/test_obsidian_writer.py` |
| `config/settings.yaml` | Model names, timeouts, vault paths, Power Automate placeholders, research settings. | Partial | High | `config/settings.yaml` |
| `.github/workflows/jarvis.yml` | Primary automation and deployment runner. | Working but validation-mode cron | High | `.github/workflows/jarvis.yml` |
| `prompts/*.md` | Intended system prompts for future Anthropic calls. | Aspirational/stubbed | High | `prompts/orchestrator.md`, `prompts/research.md`, `prompts/obsidian_writer.md` |
| `specs/001-jarvis-mvp/` | Product spec, implementation plan, contracts, quickstart. | Strong intended-state docs, partially stale status | High | `specs/001-jarvis-mvp/*.md` |
| `tests/` | Unit tests for parser, main/dry-run, routing, PII, draft staging, PA retry. | Useful but not complete | High | `tests/*.py` |
| `jarvis/inbox.md` | Operator-editable task input. Also template/no-task sentinel. | Implemented | High | `jarvis/inbox.md` |
| `prompts/route1_refresh_error_diagnosis.md` | Unrelated or legacy prompt artifact. | Suspicious/possibly abandoned | Medium | `rg --files` |

## 4. Implementation Status Assessment

### Clearly Implemented

- [Confirmed] Inbox parsing for the documented markdown format, including priority/mode validation and first-task-only behavior. Evidence: `orchestrator/utils/inbox_parser.py`, `tests/test_inbox_parser.py`.
- [Confirmed] Cleared-template detection so cron/manual no-task runs produce a no-task digest rather than a fake task. Evidence: `orchestrator/utils/inbox_parser.py`, `tests/test_inbox_parser.py`, `tests/test_orchestrator.py`.
- [Confirmed] GitHub Actions workflow for push/manual/schedule execution and Power Automate posting. Evidence: `.github/workflows/jarvis.yml`.
- [Confirmed] Power Automate webhook client with retry behavior on 429/5xx and failure log output. Evidence: `orchestrator/utils/power_automate.py`, `tests/test_power_automate.py`.
- [Confirmed] Task record and daily digest markdown generation. Evidence: `orchestrator/agents/obsidian_writer.py`, `tests/test_obsidian_writer.py`.
- [Confirmed] Draft communication staging for simple Teams/email draft requests, with `[HUMAN APPROVAL REQUIRED]`. Evidence: `orchestrator/agents/obsidian_writer.py`, Section 4 validation output in user-provided transcript.
- [Confirmed] Basic PII guard for email and simple two-word name patterns. Evidence: `orchestrator/utils/pii_guard.py`, Section 5 validation transcript, `tests/test_obsidian_writer.py`.

### Partially Implemented

- [Confirmed] AgentRun audit records exist, but token usage is currently zero because no real Anthropic calls are made. Evidence: `orchestrator/agents/*.py`, `orchestrator/utils/token_logger.py`.
- [Confirmed] Research cache behavior is local keyword search, not an LLM summarization or real semantic cache. Evidence: `orchestrator/agents/research.py`, `orchestrator/utils/vault_reader.py`.
- [Confirmed] Lesson file payloads are generated, but true append/update semantics depend on Power Automate flow behavior that is outside the repo. Evidence: `orchestrator/agents/obsidian_writer.py`, `specs/001-jarvis-mvp/contracts/webhook-payload.md`.
- [Confirmed] Power Automate output path works in operator validation, but the actual flow is not version-controlled. Artifact Evidence: user validation transcript showing SharePoint `CreateFile` status 200.
- [Confirmed] Cost calculation exists, but weekly cost rollup and nonzero token capture are not implemented. Evidence: `orchestrator/utils/token_logger.py`, `specs/001-jarvis-mvp/tasks.md`.

### Stubbed / Placeholder

- [Confirmed] Anthropic SDK is listed in `requirements.txt`, but source code does not instantiate an Anthropic client or call Claude. Evidence: `requirements.txt`, `rg` source inventory.
- [Confirmed] Prompt files exist but are not loaded by the runtime. Evidence: `prompts/*.md`, `orchestrator/agents/*.py`.
- [Confirmed] `config/settings.yaml` timeout values are not enforced in code. Evidence: `config/settings.yaml`, `orchestrator/main.py`.
- [Confirmed] GCP discovery files named in plan do not exist in the source tree. Evidence: `rg --files`, `specs/001-jarvis-mvp/plan.md`.

### Likely Planned but Not Built

- [Confirmed] `gcp_discovery.py`, `prompts/gcp_discovery.md`, `tests/test_gcp_discovery.py`, and daytime GCP mode are planned but absent. Evidence: `specs/001-jarvis-mvp/tasks.md`, `rg --files`.
- [Confirmed] Weekly usage rollup, context pruning, and cache-hit digest metrics are planned but absent. Evidence: `specs/001-jarvis-mvp/tasks.md`.
- [Confirmed] Create-or-update behavior for SharePoint files is specified but not enforced by repo code. Evidence: `specs/001-jarvis-mvp/contracts/webhook-payload.md`; Artifact Evidence: user noted duplicate output files and create-only behavior.

### Cannot Determine

- [Unverified] Whether the Power Automate flow currently performs create-or-update or create-only behavior. The repo only posts payloads; the flow itself is external.
- [Unverified] Whether GitHub Actions secrets are configured correctly in the live repo beyond previous successful validation runs.
- [Unverified] Whether OneDrive sync is reliable enough for unattended morning delivery.

## 5. Likely Build / Run / Deploy Workflows

### Local Install and Test

[Confirmed] Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

[Confirmed] Run tests:

```powershell
python -m unittest discover -s tests
```

[Confirmed] Dry-run parse behavior:

```powershell
python orchestrator/main.py --dry-run
```

Confidence: High. Evidence: `requirements.txt`, `tests/`, `orchestrator/main.py`.

### Local Real Run

[Inferred] A local real run requires `POWER_AUTOMATE_WEBHOOK_URL` in the environment. Without it, `orchestrator/main.py` prints a result but does not post files or clear `jarvis/inbox.md`.

```powershell
$env:POWER_AUTOMATE_WEBHOOK_URL = "<signed Power Automate trigger URL>"
python orchestrator/main.py
```

Confidence: High. Evidence: `_maybe_post_outputs()` in `orchestrator/main.py`.

### GitHub Actions Run

[Confirmed] A normal operator flow is: edit `jarvis/inbox.md`, commit, push to `main`, GitHub Actions runs, Python posts vault files to Power Automate, and the workflow commits the cleared inbox back to GitHub. Evidence: `.github/workflows/jarvis.yml`.

[Confirmed] The workflow can also be run manually through `workflow_dispatch`.

[Confirmed] Scheduled runs currently fire every 5 minutes because the cron was temporarily changed for validation. Evidence: `.github/workflows/jarvis.yml`.

### Deployment

[Inferred] There is no separate deployment artifact. GitHub Actions is the runtime environment. Power Automate and SharePoint are external runtime dependencies.

## 6. Configuration and Dependencies

[Confirmed] Approved dependencies are `anthropic`, `google-cloud-bigquery`, `requests`, and `pyyaml`. Evidence: `requirements.txt`, `AGENTS.md`.

[Confirmed] Required GitHub Actions secrets:

- `ANTHROPIC_API_KEY`
- `POWER_AUTOMATE_WEBHOOK_URL`

Evidence: `.github/workflows/jarvis.yml`, `specs/001-jarvis-mvp/plan.md`.

[Confirmed] `config/settings.yaml` defines model names, timeouts, vault dirs, and Power Automate placeholders. Some values are not used at runtime.

[Unverified] The live Power Automate flow must split each `vault_path` into parent folder and file name, write `content`, and respond 200. The repo cannot validate this flow directly.

## 7. Architecture Reconstruction

### Conclusion: Jarvis is a single-process sequential pipeline.

Evidence: `orchestrator/main.py` calls `parse_inbox()`, `run_orchestrator()`, conditionally `run_research()`, then `build_vault_outputs()`.

Confidence Level: High.

Alternate Interpretations: The specs describe Claude agents, but the code currently implements deterministic local functions.

Risk if Misunderstood: Future agents may assume true AI reasoning exists and build on capabilities that are not present.

Recommended Validation Step: Search for `anthropic` usage in source before planning LLM-dependent work.

### Conclusion: The durable output boundary is Power Automate, not the Git repo.

Evidence: `build_vault_outputs()` returns file payloads; `_maybe_post_outputs()` sends them to `POWER_AUTOMATE_WEBHOOK_URL`; `.gitignore` excludes generated vault dirs.

Confidence Level: High.

Alternate Interpretations: Some validation users expected files in GitHub, but current design sends them to SharePoint/Obsidian.

Risk if Misunderstood: Debugging will look in the wrong storage location.

Recommended Validation Step: Inspect SharePoint/Obsidian paths first when task/digest outputs are missing.

### Conclusion: Power Automate is a critical unversioned system boundary.

Evidence: `specs/001-jarvis-mvp/contracts/webhook-payload.md` specifies flow behavior, but no exported PA flow definition exists in repo.

Confidence Level: High.

Alternate Interpretations: The flow could be considered operator infrastructure outside source control.

Risk if Misunderstood: Repo tests can pass while production output fails or duplicates.

Recommended Validation Step: Export or document the exact PA flow steps and expressions.

### Conclusion: PII enforcement is code-level but heuristic.

Evidence: `pii_guard.py` uses regex for email and two-capitalized-word names, with a small allowlist.

Confidence Level: High.

Alternate Interpretations: Prompt-level PII hard stops exist in prompt files, but prompts are not used at runtime.

Risk if Misunderstood: False negatives are possible for non-two-word names, lowercase names, customer identifiers, and indirect PII.

Recommended Validation Step: Expand PII tests before adding real LLM calls.

### Apparent Boundaries and Data Flow

1. Operator edits `jarvis/inbox.md`.
2. GitHub Actions triggers.
3. Python parses inbox into a task dict.
4. Deterministic "agents" append AgentRun records to a TaskResult dict.
5. Obsidian writer renders markdown payloads.
6. Power Automate writes payload files into SharePoint.
7. OneDrive sync exposes files to Obsidian.
8. GitHub Actions commits cleared inbox back to `main`.

## 8. Assumptions

- [Inferred] The operator uses `main` as the active branch. Evidence: workflow pushes to current checkout and user logs reference `main`.
- [Inferred] `jarvis/` generated output dirs should not be tracked in Git. Evidence: `.gitignore`, current workflow output path.
- [Inferred] The Power Automate flow should own create/update semantics. Evidence: contract file and user validation notes about duplicate files.
- [Unverified] The SharePoint/OneDrive vault path remains stable.

## 9. Constraints

- [Confirmed] No PII storage. Evidence: `AGENTS.md`, prompt files, `pii_guard.py`.
- [Confirmed] No auto-send. Evidence: `AGENTS.md`, `obsidian_writer.py`; no email/Teams send API code found.
- [Confirmed] Approved dependencies only. Evidence: `requirements.txt`, `AGENTS.md`.
- [Confirmed] No new database. Evidence: `data-model.md` says there is no database.
- [Confirmed] Current GitHub workflow writes back to `main`, so local developers must pull/rebase before new task pushes.

## 10. Risks

- [Confirmed] Temporary cron is still active. Impact: repeated scheduled runs every 5 minutes until restored. Recommendation: restore `0 23 * * 1-5` after Section 6.
- [Confirmed] Task IDs always start with `task-001-`. Impact: collisions and overwrite/update ambiguity. Evidence: `_build_task_id()` in `orchestrator/agents/orchestrator.py`.
- [Confirmed] Power Automate smoke test always posts `jarvis/test.md` when secret exists. Impact: noisy validation and duplicate/non-task artifacts. Evidence: `.github/workflows/jarvis.yml`.
- [Confirmed] Create-only PA flow can duplicate or fail on existing files. Impact: daily digests, lessons, and repeated task names will collide. Artifact Evidence: user validation transcript.
- [Confirmed] LLM calls are not implemented. Impact: output quality is template-level, not intelligent task execution.
- [Confirmed] PII redaction is heuristic. Impact: compliance risk if real data is used before broader validation.
- [Inferred] No concurrency guard beyond the commit skip marker. Impact: multiple scheduled/manual runs may race on SharePoint files or inbox commits.

## 11. Unknowns

- [Unverified] Exact exported Power Automate flow definition.
- [Unverified] Whether SharePoint create/update expressions are now stable for nested paths.
- [Unverified] Whether scheduled no-task digest validation has passed after the parser fix.
- [Unverified] Whether current workflow has been restored from temporary cron.
- [Unverified] Whether `ANTHROPIC_API_KEY` is valid beyond presence/DNS checks.
- [Unverified] Whether the Anthropic model names `claude-sonnet-4-6` and `claude-haiku-4-5` are valid for the configured API.

## 12. Contradictions

- [Contradictory Evidence] Specs say agents call Claude Enterprise API; code does not call Anthropic. Evidence: `plan.md` vs `orchestrator/agents/*.py`.
- [Contradictory Evidence] Specs say GCP discovery is part of the larger plan; no GCP agent file exists. Evidence: `tasks.md` vs `rg --files`.
- [Contradictory Evidence] Webhook contract includes Parse JSON and create/update; operator validation found the trigger schema made Parse JSON unnecessary and create-only was initially used. Evidence: `contracts/webhook-payload.md`; Artifact Evidence: user validation transcript.
- [Contradictory Evidence] `tasks.md` checkboxes are all unchecked despite implemented files and passing tests.

## 13. Recommended Stabilization Steps

1. [Confirmed Need] Restore `.github/workflows/jarvis.yml` cron to `0 23 * * 1-5` after Section 6.
2. [Confirmed Need] Export or document the exact Power Automate flow, especially parent folder extraction, file name extraction, create-or-update behavior, and response action.
3. [Confirmed Need] Implement SharePoint create/update behavior to prevent duplicate or failed writes.
4. [Confirmed Need] Replace fixed `task-001-` task IDs with monotonic or timestamp-based IDs.
5. [Confirmed Need] Decide whether Phase 3 MVP should remain deterministic or add real Anthropic calls. If adding LLM calls, add redaction and trust-boundary tests first.
6. [Confirmed Need] Expand PII tests beyond emails and two-word names before processing real enterprise content.
7. [Confirmed Need] Add CI test execution to `.github/workflows/jarvis.yml`; currently the workflow installs dependencies and runs Jarvis but does not run unit tests.

## 14. Missing Information / Follow-ups

- Exported Power Automate flow definition.
- Current validation status for Section 6 after template fix.
- Decision on whether smoke test should stay in every run or move to manual validation only.
- Clear operator README in `jarvis/README.md`.
- Real Anthropic integration design and API error handling.
- GCP discovery phase decision and scope.
- Durable task ID allocation strategy.
- Documentation of git workflow around bot-cleared inbox commits.
