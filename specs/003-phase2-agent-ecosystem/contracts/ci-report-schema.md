# Contract: CI Agent Report Schema

**Feature**: 003-phase2-agent-ecosystem
**Contract ID**: ci-report-schema
**Version**: 1.0
**Created**: 2026-06-14

---

## Overview

The CI Agent produces two output files per bi-weekly run:

1. **Human-readable report** — `jarvis/ci/ci_report_{YYYY-MM-DD}.md` — synced to SharePoint for operator review in Obsidian/SharePoint
2. **Machine-readable scores** — `jarvis/ci/ci_scores_{YYYY-MM-DD}.json` — read by the next CI cycle to establish performance baselines

---

## Machine-Readable Scores Schema (`ci_scores_{date}.json`)

```json
{
  "ci_run_id": "string (UUID4, required)",
  "run_date": "string (ISO 8601 UTC, required)",
  "analysis_window": {
    "start": "string (ISO 8601 UTC, required)",
    "end": "string (ISO 8601 UTC, required)"
  },
  "summary": {
    "total_runs_analyzed": "integer (required)",
    "total_agent_executions": "integer (required)",
    "low_sample_warning": "boolean (required) — true if total_runs_analyzed < 5"
  },
  "agent_scores": [
    {
      "agent_name": "string (required)",
      "composite_score": "float 0.0–1.0 (required)",
      "dimensions": {
        "success_rate": "float 0.0–1.0 (required) — weight 0.25",
        "avg_output_quality": "float 0.0–1.0 (required) — weight 0.20",
        "validation_pass_rate": "float 0.0–1.0 (required) — weight 0.15",
        "token_efficiency": "float 0.0–1.0 (required) — weight 0.15",
        "latency_score": "float 0.0–1.0 (required) — weight 0.10, normalized: 1-(latency/max_observed)",
        "recovery_rate": "float 0.0–1.0 (required) — weight 0.10",
        "human_intervention_rate_inverted": "float 0.0–1.0 (required) — weight 0.05, = 1-human_intervention_rate"
      },
      "raw_metrics": {
        "total_executions": "integer (required)",
        "successful_executions": "integer (required)",
        "skipped_executions": "integer (required)",
        "avg_confidence_score": "float (required)",
        "avg_latency_ms": "integer (required)",
        "avg_tokens_per_run": "integer (required)",
        "retry_attempts": "integer (required)",
        "retry_successes": "integer (required)",
        "escalation_count": "integer (required)"
      }
    }
  ],
  "recommendations": [
    {
      "recommendation_id": "string (required) — e.g. R-001",
      "type": "string (required) — prompt_improvement | routing_change | config_change | threshold_adjustment",
      "target_agent": "string (required)",
      "current_value_ref": "string (required)",
      "proposed_change_summary": "string (required, max 300 chars)",
      "evidence": ["string (required)"],
      "ci_score_delta": "float (required) — projected improvement",
      "recommendation_tier": "string (required) — recommend | test_only | rejected",
      "risk_level": "string (required) — LOW | MED | HIGH",
      "recommendation_status": "string (required) — pending",
      "approval_inbox_text": "string (required)"
    }
  ]
}
```

**Recommendation tier thresholds**:
- `ci_score_delta ≥ 0.15` → `recommend`
- `0.05 ≤ ci_score_delta < 0.15` → `test_only`
- `ci_score_delta < 0.05` → `rejected` (not included in output)

**Low sample adjustment**: When `low_sample_warning: true`, the `recommend` threshold raises to `ci_score_delta ≥ 0.20`.

---

## Human-Readable Report Format (`ci_report_{date}.md`)

```markdown
# Jarvis CI Report — {YYYY-MM-DD}

**Analysis window**: {start} → {end}
**Runs analyzed**: {N}
**Agent executions**: {N}
{[WARNING: Low sample size — thresholds raised to 20% improvement required]}

---

## Agent Performance Summary

| Agent | Composite Score | vs. Baseline | Status |
|-------|----------------|--------------|--------|
| orchestrator | 0.93 | +0.02 | Stable |
| research | 0.79 | -0.05 | Degraded |
| obsidian_writer | 0.91 | +0.01 | Stable |

---

## Recommendations

### R-001 — [Type]: [Agent] ([Risk Level])

**Proposed change**: [plain-English description]

**Evidence**:
- [Log-based evidence item 1]
- [Log-based evidence item 2]

**Projected CI score improvement**: +{delta} ({current} → {projected})

**Risk level**: LOW | MED | HIGH

**To approve**: Commit an inbox task with:
> apply CI recommendation R-001

**To reject**: No action needed — this recommendation expires after the next CI run.

---

{Repeat for each recommendation with tier = recommend or test_only}

---

## No-Action Items

{List of changes analyzed but rejected (ci_score_delta < 5%) — brief summary only, no recommendation IDs}

---

## Next CI Run

**Scheduled**: {next Sunday or Wednesday at 11 PM}
**Open approvals expiring**: {list of pending recommendation IDs from prior cycles}
```

---

## Canonical Score Example

```json
{
  "ci_run_id": "e5f6a7b8-0005-4c3d-9a4e-567890123efg",
  "run_date": "2026-06-15T23:00:00Z",
  "analysis_window": {
    "start": "2026-06-11T23:00:00Z",
    "end": "2026-06-15T22:59:59Z"
  },
  "summary": {
    "total_runs_analyzed": 3,
    "total_agent_executions": 12,
    "low_sample_warning": true
  },
  "agent_scores": [
    {
      "agent_name": "research",
      "composite_score": 0.79,
      "dimensions": {
        "success_rate": 0.83,
        "avg_output_quality": 0.76,
        "validation_pass_rate": 0.67,
        "token_efficiency": 0.82,
        "latency_score": 0.88,
        "recovery_rate": 0.75,
        "human_intervention_rate_inverted": 0.90
      },
      "raw_metrics": {
        "total_executions": 6,
        "successful_executions": 5,
        "skipped_executions": 1,
        "avg_confidence_score": 0.76,
        "avg_latency_ms": 3800,
        "avg_tokens_per_run": 2200,
        "retry_attempts": 3,
        "retry_successes": 2,
        "escalation_count": 1
      }
    }
  ],
  "recommendations": [
    {
      "recommendation_id": "R-001",
      "type": "prompt_improvement",
      "target_agent": "research",
      "current_value_ref": "prompts/research.md v1.2",
      "proposed_change_summary": "Expand vault search scope to include /knowledge/** in addition to /tasks/**. 3 of 6 runs missed relevant notes that were in /knowledge/.",
      "evidence": [
        "Run a3f2b1c0: confidence_score 0.71 — validation noted 'thin context, may have missed knowledge notes'",
        "Run b7e1a2d0: confidence_score 0.74 — retry improved to 0.82 after manual note retrieved",
        "Run c9d3e4f5: skipped (0.54) — 2 relevant /knowledge/ notes existed but were not retrieved"
      ],
      "ci_score_delta": 0.22,
      "recommendation_tier": "recommend",
      "risk_level": "LOW",
      "recommendation_status": "pending",
      "approval_inbox_text": "apply CI recommendation R-001"
    }
  ]
}
```

---

## Constraints

- `recommendation_id` values must be globally unique across all CI runs (not just within a single report)
- The CI Agent must not generate recommendations for agents with `sample_size < 5` in `library.json`
- `approval_inbox_text` must exactly match what the inbox parser expects for CI approval tasks
- CI scores JSON files are append-only artifacts (one per run); they are never modified after the run completes
- Safety-related changes (`pii_detected` error class, draft communication flags) must always receive `risk_level: HIGH` regardless of projected score delta
