# Jarvis Learning Log

## 1. Confirmed Errors

### Power Automate Direct API Auth Failure

Error / Issue / Fragile Pattern: Initial webhook URL returned `DirectApiAuthorizationRequired`.

Evidence: Artifact Evidence: user-provided PowerShell/Power Automate validation transcript.

Context: The copied URL used the `environment.api.powerplatform.com/.../automations/direct/...` shape without signed `sp`, `sv`, and `sig` parameters.

Likely Root Cause: Trigger permission was set to tenant-authenticated and/or the copied URL was the direct invoke endpoint rather than the signed HTTP trigger URL.

Current Status: Resolved by setting trigger access to anyone and using the signed URL.

Prevention Guidance: Document expected URL shape and require `sig=` in setup checks.

Confidence Level: High.

### Parse JSON Failed with Null Content

Error / Issue / Fragile Pattern: Power Automate `Parse JSON` failed because required property `content` was null.

Evidence: Artifact Evidence: user screenshot and error text.

Context: HTTP trigger already had a request-body schema, and the Parse JSON step was parsing the wrong input.

Likely Root Cause: Duplicate parsing and incorrect content source in the flow.

Current Status: Resolved by removing Parse JSON and using `triggerBody()?['files']`.

Prevention Guidance: Keep the PA flow field mapping documented outside screenshots.

Confidence Level: High.

### SharePoint Folder Mapping Initially Flattened Paths

Error / Issue / Fragile Pattern: Files were written outside their intended subfolders.

Evidence: Artifact Evidence: user validation transcript showing file path debugging.

Context: `vault_path` values like `jarvis/digests/YYYY-MM-DD.md` must be split into parent folder and file name.

Likely Root Cause: `last(split(...))` was used for the file name while folder path was hardcoded too shallow.

Current Status: Operator validation showed nested digest path creation worked after flow adjustment.

Prevention Guidance: Use `vault_path` parent-folder extraction and keep parent folders pre-created or create them automatically.

Confidence Level: High.

### Draft Communication Section Was Empty

Error / Issue / Fragile Pattern: Section 4 output had `## Draft Communications` but `_(none)_`.

Evidence: Artifact Evidence: generated `task-001-draft-teams-message.md` provided by user; regression test in `tests/test_obsidian_writer.py`.

Context: The task requested a Teams draft, but the implementation only scanned previous agent output for draft-like text.

Likely Root Cause: No previous agent generated a draft body.

Current Status: Fixed by request-driven draft staging in `orchestrator/agents/obsidian_writer.py`.

Prevention Guidance: Keep explicit tests for request-driven draft tasks and verify no send APIs are introduced.

Confidence Level: High.

### PII Name Persisted in Vault Output

Error / Issue / Fragile Pattern: Section 5 redacted email but left a person-name pattern in the task request.

Evidence: Artifact Evidence: generated Section 5 task output; regression tests in `tests/test_obsidian_writer.py` and `tests/test_orchestrator.py`.

Context: Initial sanitizer only robustly handled email addresses.

Likely Root Cause: PII guard lacked name-like pattern redaction and the writer used the original task request text.

Current Status: Fixed for simple capitalized two-word name patterns in `orchestrator/utils/pii_guard.py`.

Prevention Guidance: Expand test cases before using real enterprise text.

Confidence Level: High.

### Cleared Inbox Template Became a Fake Task

Error / Issue / Fragile Pattern: Section 6 no-task validation created `task-001-replace-this-title-before-commit`.

Evidence: Artifact Evidence: user-provided fake task and digest; tests in `tests/test_inbox_parser.py` and `tests/test_orchestrator.py`.

Context: The cleared template was valid according to the parser.

Likely Root Cause: Only empty files returned `None`; template state was not treated as no-task.

Current Status: Fixed by template sentinel detection in `orchestrator/utils/inbox_parser.py`.

Prevention Guidance: Keep template text centralized or add a helper to avoid future drift.

Confidence Level: High.

### Git Push Rejections After Workflow Runs

Error / Issue / Fragile Pattern: Pushes were rejected with `fetch first` or `non-fast-forward`.

Evidence: Artifact Evidence: user-provided Git output; workflow commits inbox-clearing changes.

Context: GitHub Actions commits `jarvis: clear inbox after run [jarvis-skip]` back to `main`.

Likely Root Cause: Local branch fell behind remote bot commits.

Current Status: Mitigation is `git pull --rebase origin main` before new task pushes.

Prevention Guidance: Document the required rebase workflow and avoid force pushes.

Confidence Level: High.

### Python Cache Files Were Tracked

Error / Issue / Fragile Pattern: `__pycache__/*.pyc` files appeared as modified and blocked rebase.

Evidence: Artifact Evidence: user-provided `git status --short`; `.gitignore` now excludes caches.

Context: Tests generated bytecode and the files had previously been tracked.

Likely Root Cause: `.gitignore` was added after cache files entered the index.

Current Status: Resolved with `git rm --cached` guidance.

Prevention Guidance: Keep `.gitignore` before running tests in new repos.

Confidence Level: High.

## 2. Inferred Issues

### Real LLM Execution Is Absent

Evidence: `requirements.txt` lists `anthropic`, but no source code calls Anthropic.

Context: Specs describe Claude-backed agents.

Likely Root Cause: MVP implementation prioritized plumbing and validation before real model calls.

Current Status: Not implemented.

Prevention Guidance: Before adding Anthropic calls, define PII redaction boundary, prompt loading, token capture, retries, and test fixtures.

Confidence Level: High.

### Task ID Collisions Are Likely

Evidence: `_build_task_id()` always prefixes `task-001-`.

Context: Repeated tasks with the same title will collide.

Likely Root Cause: Early MVP simplification.

Current Status: Not fixed.

Prevention Guidance: Use timestamp, GitHub run ID, or persisted counter.

Confidence Level: High.

### Lesson Files Are Not Truly Append-Only From Repo Code Alone

Evidence: `obsidian_writer.py` returns only new content strings for lesson files; update/append semantics are external to PA.

Context: Data model requires append-only AgentLesson entries.

Likely Root Cause: File writes delegated to Power Automate.

Current Status: Partially implemented.

Prevention Guidance: Implement PA get-existing-content/update or move append logic into Python with a synced vault path only if allowed.

Confidence Level: Medium.

## 3. Fragile Areas

- [Confirmed] Current cron is `*/5 * * * *` for validation. Restore it after Section 6. Evidence: `.github/workflows/jarvis.yml`.
- [Confirmed] Power Automate flow is unversioned. Evidence: no exported flow file in repo.
- [Confirmed] PII detection is regex-based and allowlist-based. Evidence: `orchestrator/utils/pii_guard.py`.
- [Confirmed] Vault search is simple keyword scoring. Evidence: `orchestrator/utils/vault_reader.py`.
- [Confirmed] Workflow smoke test writes `jarvis/test.md` on every run with a PA secret. Evidence: `.github/workflows/jarvis.yml`.
- [Confirmed] GitHub Actions warns about Node.js 20 actions deprecation. Artifact Evidence: user-provided workflow warning.

## 4. Repeated Mistakes or Risk Patterns

- [Confirmed] External system behavior was initially inferred from docs rather than run-history evidence. Power Automate debugging improved once run inputs/outputs were inspected.
- [Confirmed] Placeholder/template content repeatedly behaved like real work until explicit sentinel logic was added.
- [Confirmed] Git workflow conflicts recur because automation writes to the same branch as the operator.
- [Inferred] Specs and plans have outpaced implementation, increasing the chance future agents assume features exist.

## 5. Prevention Guidance

1. Keep a "current truth" section in docs that distinguishes code behavior from planned behavior.
2. Run `python -m unittest discover -s tests` before pushing implementation fixes.
3. Run `git pull --rebase origin main` before editing `jarvis/inbox.md`.
4. Inspect Power Automate run inputs/outputs before changing Python when vault files are missing.
5. Restore the cron schedule immediately after scheduled-run validation.
6. Add regression tests for each validation failure before fixing it.
7. Do not add real LLM calls until PII guard, prompt loading, retry behavior, and token logging are designed together.

## 6. Evidence Gaps

- No exported Power Automate flow definition.
- No captured GitHub Actions logs checked into the repo.
- No screenshots or validation evidence folder checked into the repo.
- No live SharePoint/OneDrive sync diagnostics in source control.
- No documented current pass/fail matrix for Sections 1-6.
