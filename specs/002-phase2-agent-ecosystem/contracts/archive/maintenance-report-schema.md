> **DEFERRED TO PHASE 3** — Vault Maintenance (4A + 4B) requires a SharePoint read path not yet designed; deferred from Phase 2 scope. Do not implement until Phase 3 planning begins.

# Contract: Vault Maintenance Report Schema

**Feature**: 003-phase2-agent-ecosystem
**Contract ID**: maintenance-report-schema
**Version**: 1.0
**Created**: 2026-06-14

---

## Overview

The Vault Maintenance Agent produces a Markdown proposal report at `jarvis/vault/maintenance_{YYYY-MM-DD}.md` for any high-risk changes that require operator approval. Low-risk auto-fixes are committed directly to git and do not appear in this report.

---

## Proposal Report Format (`maintenance_{date}.md`)

```markdown
# Vault Maintenance Report — {YYYY-MM-DD}

**Auto-fixes applied**: {N} changes committed (see commit: {SHA})
**Proposals requiring approval**: {N}

---

## Auto-Fix Summary

The following low-risk changes were applied automatically:

| Fix Type | File | Change |
|----------|------|--------|
| broken_link | jarvis/knowledge/gcp-datasets.md | Repaired link to jarvis/tasks/task_20260510_001.md |
| naming_violation | jarvis/Knowledge/AzureCosts.md | Renamed to jarvis/knowledge/azure-costs.md |
| missing_frontmatter | jarvis/tasks/task_20260601_003.md | Added created: 2026-06-01, last_updated: 2026-06-14 |

---

## Proposals Requiring Approval

### M-001 — Duplicate Knowledge Notes

**Issue**: Two notes appear to cover the same topic.

**Affected files**:
- `jarvis/knowledge/gcp-bigquery-overview.md` (created 2026-05-10, 420 words)
- `jarvis/knowledge/bigquery-datasets.md` (created 2026-05-28, 380 words)

**Proposed action**: Merge content into `jarvis/knowledge/gcp-bigquery-overview.md` and delete `jarvis/knowledge/bigquery-datasets.md`. Links to the deleted file will be updated automatically.

**Risk**: MED — content merge requires judgment; some content may be lost if duplicated with differences.

**To approve**: Commit an inbox task with:
> apply vault maintenance proposal M-001

**To reject**: No action needed — this proposal expires after the next maintenance run.

---

### M-002 — Stale Task Record

**Issue**: Task record is older than 90 days with no references from other vault notes.

**Affected file**: `jarvis/tasks/task_20260205_001.md`
**Created**: 2026-02-05 (130 days ago)
**Last referenced by**: none

**Proposed action**: Move to `jarvis/archive/tasks/task_20260205_001.md`.

**Risk**: LOW-MED — file is preserved in archive, but search results will exclude it by default.

**To approve**: Commit an inbox task with:
> apply vault maintenance proposal M-002

**To reject**: No action needed — this proposal expires after the next maintenance run.
```

---

## Canonical JSON Representation (internal, not written to vault)

The Vault Maintenance Agent uses this internal structure before rendering the Markdown report:

```json
{
  "maintenance_run_id": "f1a2b3c4-0006-4d4e-9b5f-678901234fgh",
  "run_date": "2026-06-15T22:00:00Z",
  "auto_fixes": [
    {
      "fix_type": "broken_link",
      "file_path": "jarvis/knowledge/gcp-datasets.md",
      "description": "Repaired broken link [[task_20260510_001]] → correct path jarvis/tasks/task_20260510_001.md",
      "reversible": true
    },
    {
      "fix_type": "naming_violation",
      "file_path": "jarvis/Knowledge/AzureCosts.md",
      "description": "Renamed to jarvis/knowledge/azure-costs.md (kebab-case standard)",
      "reversible": true
    }
  ],
  "proposals": [
    {
      "proposal_id": "M-001",
      "proposal_type": "duplicate_note",
      "affected_paths": [
        "jarvis/knowledge/gcp-bigquery-overview.md",
        "jarvis/knowledge/bigquery-datasets.md"
      ],
      "description": "Two notes cover overlapping GCP BigQuery content. Recommend merge into gcp-bigquery-overview.md.",
      "risk_level": "MED",
      "approval_inbox_text": "apply vault maintenance proposal M-001",
      "status": "pending"
    },
    {
      "proposal_id": "M-002",
      "proposal_type": "stale_record",
      "affected_paths": ["jarvis/tasks/task_20260205_001.md"],
      "description": "Task record is 130 days old with no vault references. Candidate for archival.",
      "risk_level": "LOW",
      "approval_inbox_text": "apply vault maintenance proposal M-002",
      "status": "pending"
    }
  ],
  "commit_sha": "a1b2c3d4e5f6",
  "report_path": "jarvis/vault/maintenance_2026-06-15.md"
}
```

---

## Inbox Parser Extension

The inbox parser must recognize two new task types for Phase 2 approval flows:

**CI recommendation approval**:
```
Title: apply CI recommendation R-001
agents: ci_approval
```

**Vault maintenance approval**:
```
Title: apply vault maintenance proposal M-001
agents: vault_approval
```

Both task types route to a dedicated approval handler in `orchestrator/main.py` rather than the standard agent pipeline.

---

## Constraints

- Auto-fix changes must never modify the content body of any non-empty vault note
- Proposal IDs (`M-001`, `M-002`, etc.) must be globally unique across all maintenance runs
- The report must be written before the auto-fix commit is made, so operators can see what was changed in context
- A write error during auto-fix aborts all file changes for that run; the agent falls back to producing the report only (with proposed auto-fixes listed as proposals instead)
- The `jarvis/archive/` directory is the only valid destination for stale record archival
