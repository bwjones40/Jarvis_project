# Jarvis Build Documentation

## 1. Project Overview

[Confirmed] Jarvis is an internal Python workflow for operator-assigned task execution. The operator assigns work through `jarvis/inbox.md`; Jarvis parses the task, runs a sequential agent pipeline, renders markdown outputs, and optionally posts those outputs to a Power Automate webhook for SharePoint/Obsidian delivery. Evidence: `orchestrator/main.py`, `.github/workflows/jarvis.yml`, `specs/001-jarvis-mvp/spec.md`.

[Confirmed] The current implementation is mostly deterministic Python. Runtime agents still do not load prompt files or use Anthropic for task execution, but the GitHub Actions workflow now performs a real Anthropic smoke test through `orchestrator/utils/anthropic_smoke.py`. Evidence: `requirements.txt`, `prompts/*.md`, `orchestrator/agents/*.py`, `.github/workflows/jarvis.yml`, `orchestrator/utils/anthropic_smoke.py`.

[Confirmed] Phase 4-6 code now exists: Obsidian output batching/lessons, daytime GCP discovery via local `bq`, token/cost tables, weekly digest rollups, context pruning, and configurable PII handling. Evidence: `orchestrator/agents/obsidian_writer.py`, `orchestrator/agents/gcp_discovery.py`, `orchestrator/utils/token_logger.py`, `config/settings.yaml`, `tests/test_gcp_discovery.py`, `tests/test_pii_guard.py`.

[Inferred] The practical MVP is an integration and safety scaffold. It validates the workflow shape before introducing real Claude reasoning, richer semantic search, or unattended enterprise data access.

## 2. Repository Forensics Summary

[Confirmed] The repo is spec-first. The most complete intended-state documentation is in `specs/001-jarvis-mvp/`, while current code implements a subset plus some pragmatic runtime fixes discovered during validation. Evidence: `specs/001-jarvis-mvp/spec.md`, `specs/001-jarvis-mvp/plan.md`, `orchestrator/`.

[Confirmed] The live automation surface is `.github/workflows/jarvis.yml`. It runs on pushes to `jarvis/inbox.md`, a weekday 23:00 UTC cron, and manual dispatch. It installs Python 3.12, checks Anthropic secret presence/DNS resolution, runs `python orchestrator/main.py`, commits the cleared inbox when changed, and sends a Power Automate smoke-test file when the webhook secret exists.

[Confirmed] Unit tests are local-only at present. The GitHub Actions workflow does not run `python -m unittest discover -s tests`. Evidence: `.github/workflows/jarvis.yml`, `tests/`.

[Contradictory Evidence] `specs/001-jarvis-mvp/tasks.md` still lists many tasks as unchecked or describes Claude-backed implementations even when deterministic implementations and tests exist. Treat it as a historical task list, not current status. Evidence: `specs/001-jarvis-mvp/tasks.md`, `tests/*.py`, `orchestrator/*.py`.

[Confirmed] Additional future-phase specs exist under `specs/002-jarvis-phase2/` and `specs/003-phase2-agent-ecosystem/`. They describe validation, CI, vault maintenance, PR review, and prompt-library work that is not present in source code. Evidence: `specs/002-jarvis-phase2/`, `specs/003-phase2-agent-ecosystem/`.

## 3. Repository Map

| Area | Purpose | Maturity | Confidence | Evidence |
|---|---|---:|---:|---|
| `orchestrator/main.py` | CLI entry point. Loads settings, parses inbox or direct `--task`, runs agents, posts vault payloads, clears inbox after successful post. | Implemented MVP | High | `orchestrator/main.py` |
| `orchestrator/agents/orchestrator.py` | Builds `TaskResult`, applies PII mode, handles clarification checks, creates routing. | Implemented but deterministic | High | `orchestrator/agents/orchestrator.py` |
| `orchestrator/agents/research.py` | Searches local vault notes, logs cache-hit status, caps note content by configured word/token-like limit. | Partial | High | `orchestrator/agents/research.py` |
| `orchestrator/agents/gcp_discovery.py` | Daytime-only BigQuery metadata discovery through local `bq` CLI. Lists datasets/tables and summarizes read-only findings. | Implemented with environmental dependencies | High | `orchestrator/agents/gcp_discovery.py` |
| `orchestrator/agents/obsidian_writer.py` | Builds task records, daily digest, weekly cost rollup, lesson files, knowledge-note updates, and draft communication sections. | Implemented MVP | High | `orchestrator/agents/obsidian_writer.py` |
| `orchestrator/utils/inbox_parser.py` | Parses the markdown inbox contract and treats cleared template as no-task state. | Implemented MVP | High | `tests/test_inbox_parser.py` |
| `orchestrator/utils/power_automate.py` | Posts a batch of vault file payloads; retries 429/5xx and network errors; writes `jarvis/run-errors.log` on failure. Callers must pass explicit `{"vault_path": "<repo-relative>", "content": "..."}` dicts — raw `Path` objects will emit absolute paths. | Implemented, external dependency | High | `tests/test_power_automate.py` |
| `orchestrator/agents/stats_reporter.py` | Aggregates per-agent run logs from `jarvis/logs/`, computes success rate/latency/cost, writes `jarvis/ci/stats_YYYY-MM-DD.md` and `.json`, and posts both to Power Automate via explicit vault-relative paths. Triggered by `--mode stats_report`. | Implemented | High | `tests/test_stats_reporter.py`, `orchestrator/main.py` |
| `orchestrator/utils/pii_guard.py` | Regex PII helper with `strict`, `standard`, and `off` modes. | Partial and compliance-sensitive | High | `tests/test_pii_guard.py` |
| `orchestrator/utils/token_logger.py` | AgentRun formatting and estimated Claude cost calculation. | Implemented for zero-token deterministic runs | High | `tests/test_orchestrator.py`, `tests/test_obsidian_writer.py` |
| `orchestrator/utils/vault_reader.py` | Local markdown note existence, read, and keyword search. | Minimal | Medium | `orchestrator/utils/vault_reader.py` |
| `config/settings.yaml` | Model labels, timeouts, vault dirs, research limits, `pii.mode`, GCP project. | Active but not fully enforced | High | `config/settings.yaml` |
| `.github/workflows/jarvis.yml` | GitHub-hosted runtime, schedule, Anthropic smoke test, bot commit, PA smoke test. | Active | High | `.github/workflows/jarvis.yml` |
| `orchestrator/utils/usage_history.py` | Persists per-run token/cost usage to `jarvis/usage-history.json` for weekly digest rollups. | Implemented MVP | High | `orchestrator/utils/usage_history.py` |
| `prompts/*.md` | Intended system prompts for future LLM-backed agents. | Present but unused at runtime | High | `prompts/orchestrator.md`, `prompts/research.md`, `prompts/gcp_discovery.md`, `prompts/obsidian_writer.md` |
| `tests/` | Regression tests for parser, orchestrator, PII, GCP, Obsidian, Power Automate. | Useful but not exhaustive | High | `tests/*.py` |
| `specs/001-jarvis-mvp/Verifcation-evidence/` | Screenshot evidence for validation. Folder name has a typo. | Human evidence, not automated | Medium | `specs/001-jarvis-mvp/Verifcation-evidence/` |
| `specs/002-*`, `specs/003-*` | Future phase planning artifacts. | Planned, not implemented | Medium | `specs/002-jarvis-phase2/`, `specs/003-phase2-agent-ecosystem/` |
| `prompts/route1_refresh_error_diagnosis.md` | Prompt artifact not referenced by current runtime or tests. | Suspicious/possibly legacy | Medium | `prompts/route1_refresh_error_diagnosis.md` |

## 4. Implementation Status Assessment

### Clearly Implemented

- [Confirmed] Markdown inbox parsing with validation and no-task template detection. Evidence: `orchestrator/utils/inbox_parser.py`, `tests/test_inbox_parser.py`.
- [Confirmed] Sequential pipeline wiring for orchestrator, optional research, optional GCP, and Obsidian writer. Evidence: `orchestrator/main.py`.
- [Confirmed] Direct daytime task mode through `python orchestrator/main.py --task "..."`. Evidence: `orchestrator/main.py`, `tests/test_gcp_discovery.py`.
- [Confirmed] Daytime GCP discovery through read-only metadata commands: `bq ls`, `bq show --schema`. Evidence: `orchestrator/agents/gcp_discovery.py`.
- [Confirmed] Overnight GCP skip guard with message `GCP agent skipped: overnight mode, service account not provisioned`. Evidence: `orchestrator/agents/gcp_discovery.py`, `tests/test_gcp_discovery.py`.
- [Confirmed] Power Automate webhook retries and failure log creation. Evidence: `orchestrator/utils/power_automate.py`, `tests/test_power_automate.py`.
- [Confirmed] Task markdown, digest markdown, lesson file payloads, draft communication staging, and `[HUMAN APPROVAL REQUIRED]` flag. Evidence: `orchestrator/agents/obsidian_writer.py`, `tests/test_obsidian_writer.py`.
- [Confirmed] Token usage table and estimated cost display in task output, plus weekly digest rollup based on task files. Evidence: `orchestrator/agents/obsidian_writer.py`.
- [Confirmed] Configurable PII modes: `strict`, `standard`, `off`. Evidence: `orchestrator/utils/pii_guard.py`, `config/settings.yaml`, `tests/test_pii_guard.py`.
- [Confirmed] GCP fixes for Windows `bq.cmd`, `--project_id`, schema lookup failures, and empty/non-JSON table-list responses are covered by tests. Evidence: `tests/test_gcp_discovery.py`.
- [Confirmed] Stats report mode (`--mode stats_report`) aggregates `jarvis/logs/` run data, writes `jarvis/ci/stats_YYYY-MM-DD.{md,json}`, and posts to Power Automate using vault-relative `vault_dir` parameter so CI runner absolute paths are never sent as `vault_path`. Evidence: `orchestrator/agents/stats_reporter.py`, `orchestrator/main.py`, `tests/test_stats_reporter.py`.

### Partially Implemented

- [Confirmed] GitHub Actions performs a real Anthropic smoke test with `python -m orchestrator.utils.anthropic_smoke --model claude-haiku-4-5 --prompt hello`, but task agents themselves still do not use Anthropic. Evidence: `.github/workflows/jarvis.yml`, `orchestrator/utils/anthropic_smoke.py`, `orchestrator/agents/*.py`.
- [Confirmed] Prompt files describe agent roles, but runtime code does not load or execute them. Evidence: `prompts/*.md`, `orchestrator/agents/*.py`.
- [Confirmed] Weekly cost rollup now reads persisted usage entries from `jarvis/usage-history.json` plus current/local task output, but costs remain `$0.00` for deterministic agent runs until broader model-backed token usage is captured. Evidence: `orchestrator/utils/usage_history.py`, `orchestrator/main.py`, `orchestrator/agents/obsidian_writer.py`.
- [Confirmed] GCP discovery is read-only by command choice, but it depends on the operator's local `bq`/`gcloud` auth and local PATH resolution. Evidence: `orchestrator/agents/gcp_discovery.py`, validation transcripts.
- [Confirmed] Power Automate create/update behavior is specified but implemented outside the repository. Evidence: `specs/001-jarvis-mvp/contracts/webhook-payload.md`.
- [Confirmed] PII mode `off` is implemented in code and unit tests; fresh end-to-end validation is still needed because one captured run contained `[REDACTED_NAME]` markers. Artifact Evidence: user-provided Scenario 4 output attachment.

### Stubbed / Placeholder

- [Confirmed] `config/settings.yaml` timeout values are not enforced by the Python runtime. Evidence: `config/settings.yaml`, `orchestrator/main.py`.
- [Confirmed] `sharepoint_site_url` and `document_library` remain TODO/blank in config and are not consumed by Python. Evidence: `config/settings.yaml`.
- [Confirmed] Model names are labels in AgentRun records, not actual model invocations. Evidence: `orchestrator/utils/token_logger.py`, `orchestrator/agents/*.py`.

### Likely Planned but Not Built

- [Confirmed] Phase 2 agent ecosystem items such as validation agent, CI agent, vault maintenance, PR review, prompt library, and run logger are planned in `specs/003-phase2-agent-ecosystem/` but no corresponding source files exist in `orchestrator/agents/`. Evidence: `specs/003-phase2-agent-ecosystem/tasks.md`, `orchestrator/agents/`.
- [Confirmed] Real Claude-backed reasoning, prompt loading, retry policy for LLM calls, and token capture remain planned but unbuilt. Evidence: `specs/001-jarvis-mvp/tasks.md`, `orchestrator/`.

### Cannot Determine

- [Unverified] Whether the live Power Automate flow uses create-or-update, create-only, or custom path logic.
- [Unverified] Whether SharePoint/OneDrive sync is reliable for unattended morning delivery.
- [Unverified] Whether `ANTHROPIC_API_KEY` is valid for actual Anthropic API calls beyond presence and DNS checks.
- [Unverified] Whether `claude-sonnet-4-6` and `claude-haiku-4-5` are valid API model identifiers in the target Anthropic environment.

## 5. Likely Build / Run / Deploy Workflows

### Local Setup and Regression Tests

[Confirmed] Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

[Confirmed] Run unit tests:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m unittest discover -s tests
```

[Confirmed] Current observed regression baseline: `Ran 50 tests ... OK`. Artifact Evidence: local terminal run after Phase 6 documentation reconciliation.

### Local Dry Run

[Confirmed] Parse without webhook posting:

```powershell
python orchestrator/main.py --dry-run
```

[Confirmed] If the inbox is empty or cleared to template, expected output is `No task in inbox`. Evidence: `orchestrator/main.py`, `tests/test_inbox_parser.py`.

### Local Daytime GCP Run

[Confirmed] Direct GCP discovery bypasses `jarvis/inbox.md`:

```powershell
$env:POWER_AUTOMATE_WEBHOOK_URL=''
python orchestrator/main.py --task "List all BigQuery datasets in the non-prod environment"
```

[Confirmed] Required local assumptions: `bq` or a Windows shim such as `bq.cmd` is discoverable by `shutil.which`, local auth can list metadata for `config.settings.gcp.project`, and the run is daytime mode. Evidence: `orchestrator/agents/gcp_discovery.py`.

### Local Real Run With Power Automate

[Confirmed] Posting requires `POWER_AUTOMATE_WEBHOOK_URL`:

```powershell
$env:POWER_AUTOMATE_WEBHOOK_URL = "<signed Power Automate HTTP trigger URL>"
python orchestrator/main.py
```

[Confirmed] Without the webhook URL, the result is printed but files are not posted and `jarvis/inbox.md` is not cleared. Evidence: `_maybe_post_outputs()` and clear-inbox branch in `orchestrator/main.py`.

### GitHub Actions Runtime

[Confirmed] Expected operator flow:

1. Edit `jarvis/inbox.md`.
2. Commit and push.
3. GitHub Actions runs Jarvis.
4. GitHub Actions runs the Anthropic smoke test before the Jarvis task pipeline.
5. Python posts vault files to Power Automate.
6. If posting succeeds, the workflow commits a cleared inbox with `[jarvis-skip]`.
7. The workflow also commits `jarvis/usage-history.json` when present so later digest runs can roll up prior task usage.
8. Power Automate writes files to SharePoint; OneDrive exposes them to Obsidian.

Evidence: `.github/workflows/jarvis.yml`, `orchestrator/main.py`.

### Deployment

[Inferred] There is no packaged deployment artifact. The deployed system is the GitHub Actions workflow plus an external Power Automate flow.

## 6. Configuration and Dependencies

[Confirmed] Dependencies: `anthropic`, `google-cloud-bigquery`, `requests`, `pyyaml`. Evidence: `requirements.txt`.

[Confirmed] Runtime environment variables/secrets:

- `POWER_AUTOMATE_WEBHOOK_URL`: required to post vault files and clear inbox after task runs.
- `ANTHROPIC_API_KEY`: required by the GitHub Actions Anthropic smoke test, but not used by current task-agent execution code.

[Confirmed] `config/settings.yaml` active fields:

- `models.orchestrator`, `models.subagent`: used as AgentRun labels.
- `vault.root`, `vault.tasks_dir`, `vault.digests_dir`, `vault.lessons_dir`: used by main and Obsidian writer.
- `research.max_context_notes`, `research.max_tokens_per_note`, `research.cache_hit_threshold`: used by vault search/research.
- `pii.mode`: used by orchestrator, research, GCP, and Obsidian writer.
- `gcp.project`: used by GCP discovery.

[Confirmed] `jarvis/usage-history.json` is runtime state created by `append_usage_history()` after successful output posting. The workflow stages and commits it with the cleared inbox so weekly rollups can aggregate recent task usage across runs. Evidence: `orchestrator/main.py`, `orchestrator/utils/usage_history.py`, `.github/workflows/jarvis.yml`.

[Confirmed] `config/settings.yaml` weak or inactive fields:

- `timeouts.*`: configured but not enforced.
- `power_automate.sharepoint_site_url`, `power_automate.document_library`: TODO placeholders, not used by Python.
- `vault.knowledge_dir`: present, but current knowledge update behavior depends on `task_result.knowledge_updates`, not broad discovery.

## 7. Architecture Reconstruction

### Conclusion: Jarvis is a single-process sequential pipeline.

Evidence: `orchestrator/main.py` calls `parse_inbox()`, `search_notes()`, `run_orchestrator()`, optional `run_research()`, optional `run_gcp_discovery()`, and `build_vault_outputs()`.

Confidence Level: High.

Alternate Interpretations: Specs describe specialized AI agents, but current runtime uses deterministic functions with AgentRun logs.

Risk if Misunderstood: A future agent might assume Claude reasoning exists and skip implementing prompt loading, token capture, and API failure handling.

Recommended Validation Step: Search for Anthropic client construction before planning LLM-dependent features.

### Conclusion: Power Automate is the durable output boundary.

Evidence: `build_vault_outputs()` returns file payloads; `_maybe_post_outputs()` sends them to `POWER_AUTOMATE_WEBHOOK_URL`; `.gitignore` excludes generated vault output directories.

Confidence Level: High.

Alternate Interpretations: Local files under `jarvis/tasks`, `jarvis/digests`, and `jarvis/agents` may appear during tests or validation, but intended generated output is system-managed.

Risk if Misunderstood: Debugging may look in the Git repo when the true write failure is in Power Automate or SharePoint.

Recommended Validation Step: Inspect Power Automate run body and SharePoint file output for missing vault files.

### Conclusion: GCP discovery is local-operator metadata discovery, not cloud-hosted service-account automation.

Evidence: `gcp_discovery.py` shells out to local `bq`; `plan.md` says service account is deferred; overnight mode skips GCP.

Confidence Level: High.

Alternate Interpretations: `google-cloud-bigquery` is installed, but current code does not use the Python BigQuery client.

Risk if Misunderstood: Running in GitHub Actions or another machine without `bq`/auth will fail or degrade.

Recommended Validation Step: Run `where bq`, `bq ls --project_id=<project> --format=json`, then Scenario 4 locally.

### Conclusion: PII behavior is configurable, but policy posture depends on mode.

Evidence: `pii_guard.py` implements `strict`, `standard`, and `off`; `config/settings.yaml` currently sets `mode: off`.

Confidence Level: High.

Alternate Interpretations: Original project constraints said "No PII" absolutely; the updated implementation intentionally supports local-only `off` mode by user request.

Risk if Misunderstood: A future production or GitHub Actions run could leak names/emails if `off` is committed or used outside approved local validation.

Recommended Validation Step: Before sensitive runs, set `pii.mode: strict` and run Scenario 6.

### Apparent System Boundaries

- Input boundary: `jarvis/inbox.md` or CLI `--task`.
- Runtime boundary: local Python process or GitHub Actions runner.
- Output boundary: Power Automate webhook payload.
- External data boundary: local `bq` CLI for metadata-only BigQuery discovery.
- Human-approval boundary: draft communication is markdown only; no send APIs exist.

### Coupling Hotspots

- `orchestrator/main.py` owns routing order, webhook posting, direct task behavior, and inbox clearing.
- `obsidian_writer.py` mutates `task_result` while rendering outputs.
- `pii_guard.py` affects every agent and all vault text rendering.
- Power Automate path handling is outside version control but critical to output correctness.
- `power_automate.post_files()` raw-Path overload is a footgun: it calls `as_posix()` on the Path, which emits an absolute path when the caller holds an absolute Path. Any new agent posting files must pass explicit `{"vault_path": "<repo-relative>", "content": "..."}` dicts. Evidence: `orchestrator/utils/power_automate.py:77`, learning log entry "Stats Reporter Sent Absolute CI Runner Path as `vault_path`".

## 8. Assumptions

- [Inferred] `main` is the active GitHub branch for Jarvis operation. Evidence: workflow bot commit pattern and user validation logs.
- [Confirmed] Generated vault outputs should stay out of Git. Evidence: `.gitignore`.
- [Inferred] The operator is expected to run GCP discovery locally, not in GitHub Actions. Evidence: local `bq` subprocess dependency and daytime service-account deferral.
- [Inferred] `pii.mode: off` is intended for explicitly approved local validation or non-sensitive metadata work, not normal production. Evidence: `config/settings.yaml` comments and `spec.md`.

## 9. Constraints

- [Confirmed] No auto-send. There is no email or Teams API send path; drafts are markdown only. Evidence: `obsidian_writer.py`, `AGENTS.md`.
- [Confirmed] Read-only GCP. Code uses list/show metadata commands and includes a read-only summary statement. Evidence: `gcp_discovery.py`.
- [Confirmed] Approved dependencies only. Evidence: `requirements.txt`, `AGENTS.md`.
- [Confirmed] No database. The data model is markdown files plus in-memory dicts. Evidence: `specs/001-jarvis-mvp/data-model.md`.
- [Confirmed] PII behavior must match selected `pii.mode`. Evidence: `spec.md`, `pii_guard.py`.
- [Confirmed] Braden has no admin rights; future setup should avoid admin-only install paths. Evidence: `AGENTS.md`.

## 10. Risks

- [Confirmed] `pii.mode` currently defaults to `off` in committed config. Impact: local runs will not redact names or emails. Recommendation: use `strict` for sensitive runs and consider a production override/check before GitHub Actions.
- [Confirmed] End-to-end `pii.mode: off` evidence is not yet clean because one captured Scenario 4 summary still had `[REDACTED_NAME]`. Impact: validation evidence should be rerun after the Obsidian writer fix. Recommendation: rerun Scenario 4 and search output for `REDACTED`.
- [Confirmed] Task IDs always start with `task-001-`. Impact: repeated title collisions can overwrite or confuse task records. Evidence: `_build_task_id()` in `orchestrator/agents/orchestrator.py`.
- [Confirmed] Unit tests do not run in CI. Impact: regressions can land even when GitHub Actions is green. Evidence: `.github/workflows/jarvis.yml`.
- [Confirmed] Power Automate smoke test writes `jarvis/test.md` on every run with a webhook secret. Impact: noisy artifacts and possible overwrites. Evidence: `.github/workflows/jarvis.yml`.
- [Confirmed] Real LLM execution is absent. Impact: output quality is limited to template/deterministic summaries.
- [Confirmed] PII detection is regex-based. Impact: false negatives and false positives are expected outside tested patterns.
- [Inferred] Multiple manual/scheduled runs may race on SharePoint writes or bot commits. Evidence: no explicit workflow concurrency group in `.github/workflows/jarvis.yml`.

## 11. Unknowns

- [Unverified] Exact live Power Automate flow definition and whether it upserts files.
- [Unverified] Current SharePoint path extraction expressions.
- [Unverified] Whether OneDrive sync consistently surfaces files in Obsidian within target time.
- [Unverified] Whether GitHub Actions environment can ever run GCP discovery; current design implies local operator auth only.
- [Unverified] Whether Anthropic model names and credentials are valid for real model calls.
- [Confirmed] Phase 6 evidence is current in `specs/001-jarvis-mvp/Verifcation-evidence/phase-6-cost-controls/`, including screenshots for weekly cost rollup with 3 task records, context pruning AgentRun output, and research `cache_hit` logging. Evidence: `specs/001-jarvis-mvp/Verifcation-evidence/phase-6-cost-controls/6.5 Weekly cost rollup with 3 task records - Proof.png`, `specs/001-jarvis-mvp/Verifcation-evidence/phase-6-cost-controls/6.6 Context pruning AgentRun output - Proof.png`, `specs/001-jarvis-mvp/Verifcation-evidence/phase-6-cost-controls/6.7 Research cache_hit AgentRun output - Proof.png`.

## 12. Contradictions

- [Contradictory Evidence] Specs and plans say Claude Enterprise agents will execute tasks; current code records model names and the workflow now performs a real Anthropic smoke test, but task execution itself is still deterministic and not Claude-backed. Evidence: `specs/001-jarvis-mvp/plan.md`, `orchestrator/agents/*.py`, `.github/workflows/jarvis.yml`, `orchestrator/utils/anthropic_smoke.py`.
- [Contradictory Evidence] `tasks.md` still lists some implemented items as incomplete. Evidence: `specs/001-jarvis-mvp/tasks.md`, `tests/test_gcp_discovery.py`, `orchestrator/agents/gcp_discovery.py`.
- [Contradictory Evidence] `plan.md` describes `bq ls --project={project}`, but implemented code uses `--project_id={project}` because local validation showed `--project` failed. Evidence: `plan.md`, `gcp_discovery.py`, Artifact Evidence: user validation error.
- [Contradictory Evidence] Original project constraints state "No PII"; updated spec/config allow `pii.mode: off` for approved local runs. Evidence: `AGENTS.md`, `spec.md`, `config/settings.yaml`.
- [Contradictory Evidence] Webhook contract says use Parse JSON; validation found trigger-body schema access made separate Parse JSON unnecessary or fragile. Evidence: `contracts/webhook-payload.md`, Artifact Evidence: prior PA validation errors.

## 13. Recommended Stabilization Steps

1. [Confirmed Need] Add `python -m unittest discover -s tests` to `.github/workflows/jarvis.yml`.
2. [Confirmed Need] Rerun Scenario 4 after the latest PII-mode fix and capture proof that `pii.mode: off` produces no `[REDACTED_*]` markers.
3. [Confirmed Need] Decide whether committed default `pii.mode: off` is acceptable. If not, use `strict` in committed config and document how to override locally.
4. [Confirmed Need] Export or document the live Power Automate flow, including file upsert behavior.
5. [Confirmed Need] Replace fixed `task-001-` IDs with timestamp, GitHub run ID, or a durable counter.
6. [Confirmed Need] Add workflow `concurrency` to prevent overlapping scheduled/manual runs.
7. [Confirmed Need] Gate or move the Power Automate smoke test so production runs do not always write `jarvis/test.md`.
8. [Confirmed Need] Design the Anthropic client boundary before adding real LLM calls: prompt loading, PII boundary, retries, timeouts, token capture, and fixture-based tests.
9. [Confirmed Need] Clarify whether Phase 2 specs are active backlog, archive, or future-only planning.

## 14. Missing Information / Follow-ups

- Exported Power Automate flow definition or exact build notes.
- Phase 5 end-to-end rerun evidence is still a useful gap; Phase 6 evidence is current.
- Policy decision for default `pii.mode`.
- Operator README for daily use, GCP prerequisites, and git rebase after bot commits.
- Anthropic integration design.
- Unique task ID strategy.
- CI regression-test step.
- Evidence cleanup plan for the typo path `Verifcation-evidence`.

## 15. Known Git Failure Recovery

[Confirmed] The most common git failure during validation was a non-fast-forward push caused by the GitHub Actions workflow committing cleared inbox state and `jarvis/usage-history.json` back to `main`. Evidence: `.github/workflows/jarvis.yml`, recent commit history with repeated `jarvis: update run state after run [jarvis-skip]` commits.

[Confirmed] Safe recovery sequence when your local change updates `jarvis/inbox.md` or nearby validation files:

```powershell
git status --short --branch
git fetch origin
$env:GIT_EDITOR='true'
git pull --rebase origin main
```

[Confirmed] If `jarvis/inbox.md` conflicts during the rebase, keep the task content you intended to push, then continue:

```powershell
git add jarvis/inbox.md
git rebase --continue
git push origin main
```

[Confirmed] If you get stuck mid-rebase or accidentally created a detached `HEAD` commit, abort and restart the rebase flow instead of creating more commits inside the rebase:

```powershell
git rebase --abort
git fetch origin
$env:GIT_EDITOR='true'
git pull --rebase origin main
git push origin main
```
