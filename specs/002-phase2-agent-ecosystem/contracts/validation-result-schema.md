# Contract: Validation Result Schema

**Feature**: 002-phase2-agent-ecosystem
**Contract ID**: validation-result-schema
**Version**: 1.1
**Revised**: 2026-06-15

---

## Overview

The Validation Agent produces one `ValidationResult` dict after scoring each subagent output. This result is used inline by `orchestrator/main.py` to make the retry/skip/accept decision. Key fields are written to the corresponding `AgentLogEntry` in the run log.

**Scope**: The Validation Agent runs only after `research` and `obsidian_writer`. It does NOT run after `gcp_discovery` (structural validation only) or `orchestrator`.

---

## Schema

```json
{
  "agent_name": "string (required) — research | obsidian_writer",
  "run_id": "string (required)",
  "confidence_score": "float 0.0–1.0 (required)",
  "pass": "boolean (required)",
  "retry_recommended": "boolean (required)",
  "escalate": "boolean (required)",
  "quality_dimensions": {
    "relevance": "float 0.0–1.0 (required)",
    "completeness": "float 0.0–1.0 (required)",
    "actionability": "float 0.0–1.0 (required)",
    "format_adherence": "float 0.0–1.0 (required)"
  },
  "notes": "string (optional, max 300 chars)"
}
```

---

## Composite Score Formula

```
confidence_score = (relevance × 0.35) + (completeness × 0.30) +
                   (actionability × 0.25) + (format_adherence × 0.10)
```

**Dimension definitions**:
- `relevance`: output addresses the actual task request
- `completeness`: all aspects of the task are covered
- `actionability`: output gives the operator something concrete to act on today
- `format_adherence`: output matches the expected structure for this agent

---

## Decision Logic

```
confidence_score ≥ 0.90 (pass_threshold)
    → pass=true, retry_recommended=false, escalate=false → ACCEPT

0.60 ≤ confidence_score < 0.90 (retry_min_threshold)
    → pass=false, retry_recommended=true, escalate=false → RETRY ONCE
        retry score ≥ 0.80 (retry_accept_threshold) → ACCEPT (partial)
        retry score < 0.80                           → SKIP + ESCALATE

confidence_score < 0.60 (skip_threshold)
    → pass=false, retry_recommended=false, escalate=true → SKIP immediately
```

**All thresholds are configurable** in `config/settings.yaml` under the `validation:` key:
```yaml
validation:
  pass_threshold: 0.90
  retry_min_threshold: 0.60
  retry_accept_threshold: 0.80
  skip_threshold: 0.60
```

**Mutual exclusivity**: Exactly one of `{pass=true}`, `{retry_recommended=true}`, `{escalate=true}` is true in any given ValidationResult.

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
    "actionability": 0.90,
    "format_adherence": 0.88
  }
}
```

### Retry window — accepted after retry

```json
{
  "agent_name": "obsidian_writer",
  "run_id": "b7e1a2d0-0002-4f3c-9c4b-234567890bcd",
  "confidence_score": 0.74,
  "pass": false,
  "retry_recommended": true,
  "escalate": false,
  "quality_dimensions": {
    "relevance": 0.82,
    "completeness": 0.68,
    "actionability": 0.72,
    "format_adherence": 0.75
  },
  "notes": "Digest section missing weekly cost rollup. Completeness pulled composite down."
}
```

### Escalation (skip)

```json
{
  "agent_name": "obsidian_writer",
  "run_id": "c9d3e4f5-0003-4a1b-7e2c-345678901cde",
  "confidence_score": 0.51,
  "pass": false,
  "retry_recommended": false,
  "escalate": true,
  "quality_dimensions": {
    "relevance": 0.70,
    "completeness": 0.40,
    "actionability": 0.45,
    "format_adherence": 0.50
  },
  "notes": "Output is incomplete after retry. Task record body is empty."
}
```

### Synthetic pass (Validation Agent crashed)

When the Validation Agent crashes, the orchestrator constructs this synthetic result and logs the crash separately:

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
    "actionability": 0.90,
    "format_adherence": 0.90
  },
  "notes": "SYNTHETIC: Validation Agent error — assumed pass. See run log for Validation Agent error entry."
}
```

---

## Test Fixture

Set environment variable `JARVIS_VALIDATION_OVERRIDE_SCORE=<float>` to inject a synthetic score for all agents in a run. Used for testing retry/skip logic without mocking internals. Example:

```bash
JARVIS_VALIDATION_OVERRIDE_SCORE=0.45 python orchestrator/main.py --dry-run
```

This causes the Validation Agent to return the specified score for every agent it evaluates, bypassing the actual LLM call.

---

## Constraints

- `agent_name` must be `research` or `obsidian_writer` only — Validation Agent never scores itself, gcp_discovery, or orchestrator
- `confidence_score` must equal the weighted average of `quality_dimensions` (within floating-point rounding)
- `notes` must not exceed 300 characters
- The Validation Agent must never call itself recursively
