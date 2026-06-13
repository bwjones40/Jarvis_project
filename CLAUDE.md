# Jarvis MVP — Agent Context

<!-- SPECKIT START -->
**Active feature plan**: [specs/001-jarvis-mvp/plan.md](specs/001-jarvis-mvp/plan.md)
**Spec**: [specs/001-jarvis-mvp/spec.md](specs/001-jarvis-mvp/spec.md)
**Feature directory**: `specs/001-jarvis-mvp/`
<!-- SPECKIT END -->

## Project Overview

This repo builds "Jarvis" — an internal AI orchestration system that executes assigned tasks overnight and delivers results to an Obsidian vault each morning. See the spec for the full feature description.

## Key Constraints (Do Not Violate)

- **No PII**: Agents must never store names, emails, or customer data. Hard stop in every system prompt.
- **No auto-send**: All draft communications go to vault with `[HUMAN APPROVAL REQUIRED]` flag. Zero send capability in codebase.
- **Read-only GCP**: No write credentials requested or used.
- **Approved services only**: `anthropic`, `google-cloud-bigquery`, `requests`, `pyyaml`. No unapproved SaaS SDKs.

## Implementation Phases

1. Repo Skeleton + GitHub Actions
2. Inbox Parser + Orchestrator Agent
3. Research Agent
4. Obsidian Knowledge Agent + Power Automate Integration
5. GCP Discovery Agent (daytime only)
6. Cost Controls + Token Logging

## Open Items

- SharePoint site URL and document library path (needed for Phase 4 Power Automate flow)
- GCP service account IAM approval (4-8 week process; Phase 5 works without it via operator auth)
