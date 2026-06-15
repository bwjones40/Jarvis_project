# Research: Jarvis Phase 2 — Agent Ecosystem Expansion

**Feature**: 003-phase2-agent-ecosystem
**Created**: 2026-06-14
**Status**: Complete — all decisions resolved via grilling session

---

## Decision Log

### 1. Log Storage Backend

**Decision**: JSON flat files in vault, written to `jarvis/logs/{date}/{run_id}.json`, synced to SharePoint via the existing Power Automate webhook.

**Rationale**: Zero new dependencies (uses only approved services). Power Automate webhook already handles file delivery to SharePoint. Files sync to Obsidian via OneDrive. Python's `json` stdlib handles read/write. Queryable via simple file iteration from `ci_agent.py`.

**Alternatives considered**:
- SharePoint List via Graph API — requires `msal` or OAuth2 setup, new dependency
- Azure Table Storage / CosmosDB — new approved service required, overkill for current data volume (~40 records/week)
- SQLite — local only, no sync to SharePoint/Obsidian without extra work

---

### 2. Monitoring Agent Architecture

**Decision**: Monitoring logic is embedded directly in `orchestrator/main.py` as a wrapper around each agent call (retry logic, skip-degrade, escalation). Not a separate process or GitHub Actions job.

**Rationale**: Jarvis runs as a short-lived GitHub Actions job, not a persistent service. A sidecar or persistent monitor would require new infrastructure. Inline monitoring keeps the system deterministic, simple to debug, and zero-infrastructure.

**Alternatives considered**:
- Separate GitHub Actions job — adds workflow complexity, can't retry individual agents mid-pipeline
- Azure Function / persistent service — new infrastructure outside approved services

---

### 3. Recovery Mode

**Decision**: Skip and continue degraded. A failed agent (after retry exhausted) is skipped. The run continues with remaining agents. TaskResult.status = "partial". The skipped agent and its failure reason appear in the morning digest as `[HUMAN REVIEW REQUIRED]`.

**Rationale**: Maximizes the value of each run — partial output is more useful than no output. Operator always gets a digest, even if some agents failed. Failure is visible and actionable without being blocking.

---

### 4. Confidence Thresholds

**Decision**: Three-tier model with a tighter pass bar than initially suggested, self-calibrating over time.
- ≥ 0.90 → accept output
- 0.60–0.89 → retry agent once; accept if retry score ≥ 0.60
- < 0.60 → skip agent, escalate to digest

**Rationale**: Operator preference for a tighter pass bar (0.90 vs 0.80) since the system is new and building trust. Wider retry window (0.60–0.89) avoids excessive escalations while still catching low-quality outputs. Self-calibration via CI recommendations allows thresholds to converge to the right values over time.

**Self-calibration trigger**: When 20+ scored executions exist for an agent, CI Agent evaluates whether threshold adjustments would improve the success/escalation balance and proposes changes in the next bi-weekly report.

---

### 5. CI Agent Trigger

**Decision**: Bi-weekly batch — Sunday and Wednesday nights at 11 PM (`cron: "0 23 * * 0,3"`).

**Rationale**: Gives 2–3 overnight runs per cycle on Wednesday (Mon/Tue data) and ~5 runs per cycle on Sunday (Wed–Fri data). Enough signal to make meaningful comparisons. More frequent than weekly while avoiding the noise of per-run analysis.

**Note**: Wednesday CI runs will have lower sample size (2–3 runs). Recommendation threshold automatically raises to require 20% improvement (vs 15%) when sample size is < 5 run cycles.

---

### 6. Prompt Library Storage

**Decision**: Prompts stay in the repo as `.md` files in `prompts/`. A central metadata index `prompts/library.json` tracks all versioning, tagging, performance data, and approval status. Archived prompt versions stored in `prompts/versions/`.

**Rationale**: Git provides the version control audit trail. `library.json` is the single queryable source of truth for the CI Agent. Zero new storage infrastructure needed. Human-readable prompt files remain editable.

---

### 7. CI Approval Flow

**Decision**: Operator approves CI recommendations via inbox task (e.g., `apply CI recommendation R-001`). Jarvis applies the change on the next run.

**Rationale**: Reuses the existing inbox-as-command-interface pattern already built in Phase 1. No new tooling or UI required. Approval is explicit (requires deliberate operator action), auditable (inbox commit in git history), and reversible (every applied change is a git commit).

---

### 8. New Agents — Phase 2 Scope

**Decision**: Four new agents in Phase 2:
1. **Validation Agent** (claude-haiku-4-5) — inline quality scoring after every agent
2. **CI Agent** (claude-sonnet-4-6) — bi-weekly log analysis and recommendations
3. **Vault Maintenance Agent** (claude-haiku-4-5) — weekly vault organization
4. **PR Review Agent** (claude-sonnet-4-6) — on-demand GitHub PR analysis

**Rationale**: Validation Agent is the highest-leverage addition (enables all recovery logic and feeds CI). CI Agent is the strategic value-add. Vault Maintenance solves a practical problem that grows with the vault. PR Review adds immediate daily utility.

**Out of scope for Phase 2**: Email Classification Agent (absorbing pm_workflow), overnight GCP Discovery (blocked by service account).

---

### 9. Vault Maintenance Agent Scope

**Decision**: Auto-handle low-risk actions without approval; propose high-risk actions via inbox.
- **Auto-fix**: broken links, naming convention violations, missing frontmatter, orphaned empty files
- **Propose**: duplicate notes, stale records (>90 days), wrong-folder notes, merge candidates

**Rationale**: Low-risk actions are reversible via git. High-risk actions touch content or reduce note count — require operator judgment.

---

### 10. Build Sequence

**Decision**: Logging → Validation → CI → Vault Maintenance → PR Review

**Rationale**: Logging must come first — without structured JSON data, CI Agent has nothing to analyze. Validation Agent must come before CI — without quality scores, CI scoring dimensions are incomplete. Vault Maintenance and PR Review are independent and added once the core observability foundation is stable.

---

### 11. pm_workflow Integration

**Decision**: Phase 2 = Jarvis writes outputs to `Jarvis/` path in the same SharePoint library where pm_workflow writes to `PM/`. No changes to pm_workflow scripts.

**Background**: pm_workflow is a set of PowerShell scripts that scrape Outlook/SharePoint, classify emails, and write briefs/tracking logs to SharePoint. It is a separate system, not a Jarvis component.

**Phase 3+ intent**: CI Agent will eventually identify overlap between pm_workflow classification and Jarvis Research Agent, and propose a dedicated Email Classification Agent to absorb the PowerShell logic. pm_workflow scripts will be deprecated at that point.

---

## Open Items

None. All Phase 2 technical decisions are resolved.

**Deferred to Phase 3+**:
- Email Classification Agent (absorbs pm_workflow)
- Overnight GCP Discovery (blocked by GCP service account, 4-8 week IAM approval)
- Autonomous A/B prompt testing
- Multi-operator support
