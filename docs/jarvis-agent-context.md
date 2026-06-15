# Jarvis Future Agent Context

## 1. What Jarvis Appears to Be

[Confirmed] Jarvis is a Python/GitHub Actions MVP for operator-assigned task processing. The main input is `jarvis/inbox.md`; the main output is markdown payloads posted to Power Automate for SharePoint/Obsidian delivery. Evidence: `orchestrator/main.py`, `.github/workflows/jarvis.yml`.

[Confirmed] Current "agents" are deterministic Python functions that append AgentRun records. They do not currently call Claude, despite model labels, prompt files, and the Anthropic dependency. Evidence: `orchestrator/agents/*.py`, `requirements.txt`, `prompts/*.md`.

[Confirmed] Phase 4-6 implementation is present: Obsidian task/digest/lesson outputs, Power Automate retry/error handling, daytime GCP discovery, token/cost tables, weekly rollups, context cap/cache-hit flags, and configurable PII modes. Evidence: `orchestrator/agents/obsidian_writer.py`, `orchestrator/agents/gcp_discovery.py`, `orchestrator/utils/pii_guard.py`, `tests/*.py`.

## 2. Current Confidence Map

| Topic | Status | Confidence | Evidence |
|---|---|---:|---|
| Inbox parsing | Implemented, with template no-task sentinel | High | `orchestrator/utils/inbox_parser.py`, `tests/test_inbox_parser.py` |
| GitHub workflow | Implemented, weekday 23:00 UTC cron, push/manual triggers | High | `.github/workflows/jarvis.yml` |
| Power Automate posting | Implemented in Python; live flow external | High | `orchestrator/utils/power_automate.py` |
| Obsidian output | Task, digest, lesson, knowledge payloads generated | High | `orchestrator/agents/obsidian_writer.py` |
| Draft safety | Drafts are markdown-only and flagged | High | `tests/test_obsidian_writer.py` |
| PII modes | `strict`, `standard`, `off` implemented | High | `orchestrator/utils/pii_guard.py`, `tests/test_pii_guard.py` |
| GCP discovery | Implemented for local daytime `bq` metadata discovery | High | `orchestrator/agents/gcp_discovery.py` |
| Weekly cost rollup | Implemented, but token counts are zero until real LLM calls | High | `orchestrator/agents/obsidian_writer.py` |
| Real Anthropic calls | Not implemented | High | no source usage of Anthropic client |
| Power Automate upsert | Required but not verifiable from repo | Medium | `contracts/webhook-payload.md` |
| Phase 2 ecosystem agents | Planned only | High | `specs/003-phase2-agent-ecosystem/` |

## 3. What Is Stable vs Uncertain

### Stable

- [Confirmed] `python -m unittest discover -s tests` is the regression command.
- [Confirmed] `python orchestrator/main.py --dry-run` is the local parse/dry-run command.
- [Confirmed] `python orchestrator/main.py --task "..."` creates a direct daytime GCP discovery task.
- [Confirmed] `POWER_AUTOMATE_WEBHOOK_URL` controls whether outputs are posted and inbox is cleared.
- [Confirmed] No send API exists for Teams or email.
- [Confirmed] GCP discovery uses metadata commands and summarizes with a no-data-modified statement.

### Uncertain

- [Unverified] Live Power Automate create/update behavior.
- [Unverified] Fresh `pii.mode: off` end-to-end proof after the latest sanitizer-path fix.
- [Unverified] Actual Anthropic API/model validity.
- [Unverified] Whether SharePoint/OneDrive sync timing meets the morning workflow target.
- [Unverified] Whether Phase 2 specs are active backlog or archived planning.

## 4. Critical Files and Why They Matter

- `AGENTS.md`: project-specific operating constraints, including no auto-send, read-only GCP, approved dependencies, and enterprise environment notes.
- `.github/workflows/jarvis.yml`: live automation. Changes affect triggers, schedule, bot commits, smoke test, secrets, and runtime.
- `config/settings.yaml`: active config for vault paths, research caps, `pii.mode`, and GCP project.
- `orchestrator/main.py`: runtime entry point and highest-coupling file.
- `orchestrator/utils/inbox_parser.py`: protects against fake tasks and malformed task input.
- `orchestrator/agents/orchestrator.py`: task ID, routing, PII stop/clarification logic.
- `orchestrator/agents/research.py`: vault search, cache-hit behavior, context cap.
- `orchestrator/agents/gcp_discovery.py`: local `bq` integration and read-only GCP behavior.
- `orchestrator/agents/obsidian_writer.py`: vault markdown shape, draft staging, weekly rollup, lesson/knowledge payload generation.
- `orchestrator/utils/pii_guard.py`: compliance-sensitive redaction/detection behavior.
- `orchestrator/utils/power_automate.py`: webhook contract, retry policy, `jarvis/run-errors.log`.
- `tests/`: current regression safety net. Local tests currently passed with 40 tests.
- `specs/001-jarvis-mvp/`: intended MVP behavior and validation scenarios.
- `docs/jarvis-mvp-verification-guide.md`: operator validation guide.

## 5. Dangerous Areas / Change Risks

- [Confirmed] Changing `.github/workflows/jarvis.yml` changes live automation and can create repeated runs, bot commits, or missing output.
- [Confirmed] Changing `pii_guard.py` or forgetting to pass `pii_mode` can create compliance regressions.
- [Confirmed] Changing `obsidian_writer.py` can alter vault file paths, digest content, draft safety, and lesson updates.
- [Confirmed] Changing `gcp_discovery.py` can break local Windows CLI compatibility or accidentally expose schema/raw JSON.
- [Confirmed] Changing Power Automate outside the repo can break production output while tests still pass.
- [Confirmed] Committing `pii.mode: off` changes safety posture for anyone running the repo.
- [Inferred] Adding Anthropic calls without a boundary design can leak prompt context, lose token accounting, or create hidden costs.

## 6. What to Validate First

1. `git status --short` and identify user/evidence changes before editing.
2. `config/settings.yaml` `pii.mode` is intentional for the run.
3. `python -m unittest discover -s tests` passes with `PYTHONDONTWRITEBYTECODE=1`.
4. `.github/workflows/jarvis.yml` schedule is intentional and not in temporary validation mode.
5. Power Automate can write nested `jarvis/tasks`, `jarvis/digests`, and `jarvis/agents` paths.
6. For GCP work: `where bq`, `bq ls --project_id=<project> --format=json`, then Scenario 4.
7. For PII mode changes: search run output and vault files for `REDACTED`, names, and emails appropriate to the selected mode.

## 7. Safe Starting Points for Improvement

- Add local unit tests to GitHub Actions.
- Export or document the Power Automate flow.
- Add unique task IDs.
- Add workflow concurrency.
- Gate the Power Automate smoke test behind manual dispatch or a separate validation flag.
- Centralize inbox template text between `main.py` and parser tests.
- Add a production-safety check around `pii.mode: off`.

## 8. Recommended Continuous Improvement Backlog

1. Rerun Scenario 4 and capture clean `pii.mode: off` proof.
2. Decide committed default for `pii.mode`.
3. Add CI unit tests.
4. Document/export Power Automate flow.
5. Implement unique task ID allocation.
6. Add workflow concurrency.
7. Split smoke test from normal production runs.
8. Implement Anthropic client wrapper only after prompt loading, PII boundaries, retries, timeouts, and token logging are designed.
9. Clarify and prioritize `specs/002-*` and `specs/003-*`.
10. Add operator troubleshooting docs for git conflicts, bq auth, and Power Automate failures.

## 9. What a New Agent Should Read First

1. `AGENTS.md`
2. `docs/jarvis-build-documentation.md`
3. `docs/jarvis-learning-log.md`
4. `docs/jarvis-mvp-verification-guide.md`
5. `specs/001-jarvis-mvp/spec.md`
6. `specs/001-jarvis-mvp/plan.md`
7. `specs/001-jarvis-mvp/contracts/inbox-schema.md`
8. `specs/001-jarvis-mvp/contracts/task-result-schema.md`
9. `specs/001-jarvis-mvp/contracts/webhook-payload.md`
10. `.github/workflows/jarvis.yml`
11. `config/settings.yaml`
12. `orchestrator/main.py`
13. `orchestrator/agents/gcp_discovery.py`
14. `orchestrator/agents/obsidian_writer.py`
15. `orchestrator/utils/pii_guard.py`
16. `tests/test_gcp_discovery.py`
17. `tests/test_obsidian_writer.py`
18. `tests/test_pii_guard.py`
