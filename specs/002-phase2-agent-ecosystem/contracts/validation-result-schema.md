# Contract: Validation Result Schema

**Feature**: 003-phase2-agent-ecosystem
**Contract ID**: validation-result-schema
**Version**: 1.0
**Created**: 2026-06-14

---

## Overview

The Validation Agent produces one `ValidationResult` dict after scoring each subagent's output. This result is used inline by `orchestrator/main.py` to make the retry/skip/escalate decision, and its key fields (`confidence_score`, `validation_pass`) are written to the `AgentLogEntry` in the run log.

---

## Schema

```json
{
  "agent_name": "string (required)",
  "run_id": "string (required)",
  "confidence_score": "float 0.0–1.0 (required)",
  "pass": "boolean (required)",
  "retry_recommended": "boolean (required)",
  "escalate": "boolean (required)",
  "quality_dimensions": {
    "relevance": "float 0.0–1.0 (required)",
    "completeness": "float 0.0–1.0 (required)",
    "compliance": "float 0.0–1.0 (required)",
    "format_adherence": "float 0.0–1.0 (required)"
  },
  "notes": "string (optional, max 300 chars)",
  "calibration_sample_size": "integer (optional)"
}
```

---

## Decision Logic

The orchestrator reads `ValidationResult` and applies this decision tree:

```
confidence_score ≥ 0.90          → pass=true,  retry_recommended=false, escalate=false → ACCEPT
0.60 ≤ confidence_score < 0.90   → pass=false, retry_recommended=true,  escalate=false → RETRY ONCE
  └─ retry score ≥ 0.60          → pass=true (partial), escalate=false                 → ACCEPT
  └─ retry score < 0.60          → pass=false, escalate=true                           → SKIP
confidence_score < 0.60          → pass=false, retry_recommended=false, escalate=true  → SKIP
```

**Mutual exclusivity**: Only one of `{pass=true}`, `{retry_recommended=true}`, `{escalate=true}` should be true in any given ValidationResult.

---

## Composite Score Calculation

The `confidence_score` is a weighted average of the four quality dimensions:

```
confidence_score = (relevance × 0.35) + (completeness × 0.30) +
                   (compliance × 0.25) + (format_adherence × 0.10)
```

Dimension weights reflect priority: task relevance and completeness matter most; format is least critical.

---

## Canonical Examples

### High-confidence pass

```json
{
  "agent_name": "research",
  "run_id": "a3f2b1c0-0001-4d2e-8b3a-123456789abc",
  "confidence_score": 0.92,
  "pass": true,
  "retry_recommended": false,
  "escalate": false,
  "quality_dimensions": {
    "relevance": 0.95,
    "completeness": 0.91,
    "compliance": 1.00,
    "format_adherence": 0.88
  },
  "calibration_sample_size": 8
}
```

### Retry window

```json
{
  "agent_name": "gcp_discovery",
  "run_id": "b7e1a2d0-0002-4f3c-9c4b-234567890bcd",
  "confidence_score": 0.74,
  "pass": false,
  "retry_recommended": true,
  "escalate": false,
  "quality_dimensions": {
    "relevance": 0.82,
    "completeness": 0.68,
    "compliance": 1.00,
    "format_adherence": 0.72
  },
  "notes": "Output covered only 2 of 4 requested datasets. Completeness score pulled the composite down.",
  "calibration_sample_size": 3
}
```

### Escalation

```json
{
  "agent_name": "obsidian_writer",
  "run_id": "c9d3e4f5-0003-4a1b-7e2c-345678901cde",
  "confidence_score": 0.54,
  "pass": false,
  "retry_recommended": false,
  "escalate": true,
  "quality_dimensions": {
    "relevance": 0.70,
    "completeness": 0.45,
    "compliance": 0.80,
    "format_adherence": 0.50
  },
  "notes": "Draft communication section is incomplete after retry. Compliance flagged possible PII pattern.",
  "calibration_sample_size": 12
}
```

### Validation Agent itself failed (fallback)

When the Validation Agent crashes, the orchestrator does **not** receive a ValidationResult. Instead it constructs a synthetic pass result:

```json
{
  "agent_name": "research",
  "run_id": "d1e2f3a4-0004-4b2c-8f3d-456789012def",
  "confidence_score": 0.90,
  "pass": true,
  "retry_recommended": false,
  "escalate": false,
  "quality_dimensions": {
    "relevance": 0.90,
    "completeness": 0.90,
    "compliance": 0.90,
    "format_adherence": 0.90
  },
  "notes": "SYNTHETIC: Validation Agent error — assumed pass. See run log for Validation Agent error details.",
  "calibration_sample_size": null
}
```

---

## Constraints

- `compliance` must be 1.00 if the output passed PII guard; must be 0.0 if PII was detected
- `notes` must not contain PII
- `confidence_score` must equal the weighted average of `quality_dimensions` (within floating-point rounding)
- The Validation Agent prompt must never be applied to Validation Agent's own output (no self-scoring)
