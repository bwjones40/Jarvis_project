# Research: Jarvis Phase 2 — Agent Ecosystem Foundation

**Feature**: 002-phase2-agent-ecosystem
**Revised**: 2026-06-15
**Status**: All decisions resolved — grilling session 2026-06-15

---

## Decision Log

### D-01: LLM Integration Approach

**Decision**: Wire real Anthropic API calls into `research.py` and `obsidian_writer.py` as Phase 0 prerequisites. Load prompt files from `prompts/` at runtime using `pathlib.Path`. Implement a single retry on `anthropic.APIError` with 10-second backoff before raising.

**Rationale**: Phase 1 agents produce deterministic template output. Validation Agent scores and token logs are meaningless until real LLM output exists. Phase 0 wiring is the prerequisite gate for all other Phase 2 work.

**Alternatives considered**: Wire all agents simultaneously — rejected; sequential wiring reduces blast radius if the first integration surfaces unexpected behavior.

---

### D-02: Logging Storage

**Decision**: JSON flat files at `jarvis/logs/{YYYY-MM-DD}/{run_id}.json`, included in the Power Automate webhook payload alongside existing Markdown vault files.

**Rationale**: No new infrastructure, no new dependencies, uses the proven delivery path validated in Phase 1.

**Alternatives considered**: SQLite — rejected (no approved dependency); separate API endpoint — rejected (no approved SaaS SDKs).

---

### D-03: PII Enforcement Boundary

**Decision**: PII enforcement applies only at the Anthropic API boundary. SharePoint-bound outputs within the Tyson Microsoft 365 tenant have no PII enforcement requirement. Committed default changes from `off` to `standard`.

**Rationale**: The tenant boundary is the appropriate enforcement point. Internal SharePoint data already contains task content from Phase 1 with no issue.

---

### D-04: Validation Agent Scope

**Decision**: Validates `research` and `obsidian_writer` only. `gcp_discovery` uses structural validation (exit code + JSON parse). `orchestrator` is not validated.

**Rationale**: `gcp_discovery` correctness is structural, not subjective — a parse check is sufficient and costs nothing.

---

### D-05: Validation Thresholds

**Decision**: Three-tier, all configurable in `settings.yaml`:
- `pass_threshold: 0.90` — accept
- `retry_min_threshold: 0.60` — retry once
- `retry_accept_threshold: 0.80` — accept retry if ≥ this; otherwise skip
- `skip_threshold: 0.60` — skip immediately if initial score < this

---

### D-06: Validation Scoring Dimensions

**Decision**: `confidence_score = (relevance × 0.35) + (completeness × 0.30) + (actionability × 0.25) + (format_adherence × 0.10)`

Replacing original `compliance` dimension with `actionability` (output gives operator something concrete to act on).

**Rationale**: Compliance is enforced at the API boundary (D-03). Actionability is a distinct signal not captured by relevance or completeness.

---

### D-07: Validation Agent Crash Handling

**Decision**: Crash returns synthetic pass (`confidence_score: 0.90`, `notes: "SYNTHETIC: Validation Agent error"`). Crash logged separately. Pipeline continues.

**Rationale**: Validation Agent must never be a single point of failure for the overnight pipeline.

---

### D-08: Task ID Strategy

**Decision**: `task-{GITHUB_RUN_ID}-{slug}` in Actions; `task-{YYYYMMDD-HHMMSS}-{slug}` for local runs.

**Rationale**: `GITHUB_RUN_ID` is unique per run and links directly to the Actions log. Timestamp fallback is sufficient locally.

---

### D-09: Workflow Concurrency

**Decision**: `concurrency: group: jarvis-run, cancel-in-progress: false`. Second run queues, does not cancel.

**Rationale**: Mid-run cancellation risks partial logs and uncommitted vault files.

---

### D-10: Power Automate Upsert

**Decision**: Check file existence before writing. If exists: full overwrite. If new: create.

**Rationale**: Current always-create behavior produces duplicate files across re-runs. Replace produces one authoritative file per vault path.

---

### D-11: Monitoring Scope

**Decision**: Two outputs:
1. Digest quality summary table (per-run, in morning digest)
2. Bi-weekly stats report (separate job, `0 23 * * 0,2`, no LLM)

**Rationale**: Per-run visibility + trend visibility. Full CI recommendation engine deferred to Phase 3.

---

### D-12: Stats Report Analysis Window

**Decision**: Start at `analysis_window_end` from most recent `jarvis/ci/stats_*.json`. First run: all available logs.

**Rationale**: Non-overlapping windows make trend comparison clean.

---

### D-13: Model Selection

| Agent | Model |
|-------|-------|
| `orchestrator.py` | `claude-sonnet-4-6` |
| `research.py` | `claude-haiku-4-5` |
| `obsidian_writer.py` | `claude-sonnet-4-6` |
| `validation.py` | `claude-haiku-4-5` |
| Stats report | No model (pure aggregation) |

**Rationale**: Sonnet for digest synthesis (operator reads daily) and routing decisions. Haiku for structured scoring and search tasks.

---

### D-14: Deferred to Phase 3

| Item | Reason |
|------|--------|
| CI recommendation engine | Needs weeks of Validation Agent data first |
| PR Review Agent | Deprioritized in favor of foundational observability |
| Vault Maintenance (4A + 4B) | GitHub Actions runner cannot access SharePoint vault files |
| Prompt Library (`library.json`) | No consumer in Phase 2 |

---

### D-15: Node.js 24 Action Update

**Decision**: Update `actions/checkout` and `actions/setup-python` to latest patch versions targeting Node.js 24. Remove `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` workaround.

**Rationale**: Workaround suppresses warning but does not fix the root cause.
