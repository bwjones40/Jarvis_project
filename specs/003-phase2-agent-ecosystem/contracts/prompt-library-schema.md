# Contract: Prompt Library Schema

**Feature**: 003-phase2-agent-ecosystem
**Contract ID**: prompt-library-schema
**Version**: 1.0
**Created**: 2026-06-14

---

## Overview

`prompts/library.json` is the central metadata index for all agent prompts. It is the single source of truth for prompt versioning, approval status, tagging, and performance history.

**Writers**:
- `orchestrator/agents/ci_agent.py` — updates `performance` metrics and `ci_notes` after each bi-weekly analysis
- `orchestrator/main.py` (CI approval handler) — bumps `version`, archives old version, updates `status` when operator approves a CI recommendation

**Readers**:
- `orchestrator/agents/ci_agent.py` — reads current performance baselines for comparison
- `orchestrator/agents/validation.py` — reads `calibration_sample_size` to determine self-calibration readiness
- Any agent that needs to reference its current `prompt_id` for the run log

---

## Schema

```json
{
  "schema_version": "string (required) — e.g. '1.0'",
  "last_updated": "string (ISO 8601 UTC, required)",
  "prompts": [
    {
      "prompt_id": "string (required) — format: {agent}_{version} e.g. 'research_v1.2'",
      "title": "string (required)",
      "file": "string (required) — repo-relative path to current prompt file",
      "linked_agent": "string (required) — agent_name value from run log",
      "use_case": "string (required)",
      "tags": ["string (required)"],
      "status": "string (required) — draft | approved | testing | deprecated",
      "version": "string (required) — e.g. '1.2'",
      "version_history": [
        {
          "version": "string (required)",
          "date": "string (ISO 8601 date, required)",
          "file": "string (required) — repo-relative path to archived file",
          "notes": "string (required)",
          "applied_by": "string (optional) — ci_recommendation:R-001 | operator"
        }
      ],
      "performance": {
        "avg_confidence_score": "float 0.0–1.0 (required)",
        "validation_pass_rate": "float 0.0–1.0 (required)",
        "avg_latency_ms": "integer (required)",
        "avg_tokens_per_run": "integer (required)",
        "sample_size": "integer (required)",
        "last_evaluated": "string (ISO 8601 date, required)"
      },
      "ci_notes": "string (optional, max 500 chars)"
    }
  ]
}
```

---

## Canonical Example

```json
{
  "schema_version": "1.0",
  "last_updated": "2026-06-14T23:00:00Z",
  "prompts": [
    {
      "prompt_id": "research_v1.2",
      "title": "Research Agent — Vault Context Retrieval",
      "file": "prompts/research.md",
      "linked_agent": "research",
      "use_case": "Retrieve relevant vault context before Anthropic API call; use cache hit if confidence ≥ 0.8",
      "tags": ["research", "context", "vault", "cache-hit"],
      "status": "approved",
      "version": "1.2",
      "version_history": [
        {
          "version": "1.0",
          "date": "2026-05-01",
          "file": "prompts/versions/research_v1.0.md",
          "notes": "Initial MVP prompt",
          "applied_by": "operator"
        },
        {
          "version": "1.1",
          "date": "2026-05-20",
          "file": "prompts/versions/research_v1.1.md",
          "notes": "Added explicit cache hit instruction and output format constraint",
          "applied_by": "operator"
        },
        {
          "version": "1.2",
          "date": "2026-06-01",
          "file": "prompts/versions/research_v1.2.md",
          "notes": "Tightened output format; reduced verbosity in context summary section",
          "applied_by": "ci_recommendation:R-003"
        }
      ],
      "performance": {
        "avg_confidence_score": 0.84,
        "validation_pass_rate": 0.79,
        "avg_latency_ms": 3100,
        "avg_tokens_per_run": 2100,
        "sample_size": 12,
        "last_evaluated": "2026-06-11"
      },
      "ci_notes": "3 of 12 runs landed in retry window (0.60–0.89). CI R-001 proposes expanding vault search scope to /knowledge/** in addition to /tasks/**. Pending approval."
    },
    {
      "prompt_id": "orchestrator_v1.0",
      "title": "Orchestrator Agent — Task Routing",
      "file": "prompts/orchestrator.md",
      "linked_agent": "orchestrator",
      "use_case": "Parse inbox task and determine which subagents are needed",
      "tags": ["orchestrator", "routing", "classification", "pii-guard"],
      "status": "approved",
      "version": "1.0",
      "version_history": [
        {
          "version": "1.0",
          "date": "2026-05-01",
          "file": "prompts/versions/orchestrator_v1.0.md",
          "notes": "MVP baseline — stable",
          "applied_by": "operator"
        }
      ],
      "performance": {
        "avg_confidence_score": 0.93,
        "validation_pass_rate": 0.92,
        "avg_latency_ms": 4800,
        "avg_tokens_per_run": 3200,
        "sample_size": 12,
        "last_evaluated": "2026-06-11"
      },
      "ci_notes": "Strong performer. No recommendations pending."
    }
  ]
}
```

---

## Version Archive Convention

When a prompt is updated via an approved CI recommendation:

1. Current file is copied to `prompts/versions/{agent}_v{old_version}.md`
2. New prompt content is written to `prompts/{agent}.md` (same path)
3. `library.json` is updated: `version` bumped, `version_history` entry added, `performance` reset (sample_size = 0)
4. The CI recommendation's `recommendation_status` is updated to `applied`

**Example**: Approving R-001 on `research_v1.2`:
- `prompts/research.md` → copied to `prompts/versions/research_v1.2.md`
- New content written to `prompts/research.md`
- library.json: `prompt_id` becomes `research_v1.3`, `version` becomes `"1.3"`, new version_history entry with `applied_by: "ci_recommendation:R-001"`

---

## Constraints

- `prompt_id` must match pattern `{linked_agent}_v{version}` exactly
- `status` transitions: only `draft` → `approved` or `testing` → `approved` → `deprecated`; a prompt cannot go from `deprecated` back to `approved` (create a new version instead)
- `performance.sample_size` resets to 0 when a new version is applied; CI Agent must not recommend based on < 5 samples
- `ci_notes` is overwritten (not appended) on each CI cycle
- `library.json` is committed as part of the CI approval inbox task run, not during CI Agent analysis
