# Research: Jarvis MVP — AI Command Center

**Created**: 2026-06-13
**Feature**: [spec.md](spec.md)

---

## Decision 1: GitHub Actions Trigger Pattern

**Decision**: Use `on: push: paths: ['jarvis/inbox.md']` with a secondary `on: schedule` cron trigger for nightly runs.

**Rationale**: GitHub's native `paths` filter is the simplest reliable approach. It triggers only when `jarvis/inbox.md` changes on push, which is exactly the desired behavior. The cron trigger handles nightly digest runs independently of task assignment. No third-party Actions needed for MVP.

**Alternatives considered**:
- `dorny/paths-filter` action: More granular (per-job/step), but overkill for this single-file pattern
- Polling-based: Rejected; GitHub-native triggers are free and reliable

**Resolved**: No clarification needed. Standard pattern.

---

## Decision 2: Power Automate → SharePoint Write Pattern

**Decision**: Use Power Automate's "When an HTTP request is received" trigger (standard connector, no premium license) combined with the SharePoint "Create file" action to write markdown files to the vault document library.

**Rationale**: This is a well-established, premium-free pattern. GitHub Actions POSTs a JSON payload to the PA flow's HTTP webhook URL. PA extracts filename and content from the payload and calls the SharePoint connector to create/update the file. OneDrive then syncs the file to the local Obsidian vault automatically.

**Alternatives considered**:
- Graph API direct upload: Requires Azure app registration and OAuth token management in GitHub Actions; adds complexity without benefit for MVP
- SharePoint REST API direct: Same complexity issue, plus requires enterprise auth from the runner

**Payload shape**: `{ "filename": "jarvis/digests/2026-06-13.md", "content": "<base64 or raw markdown>" }`

**Resolved**: No premium connectors required. Confirmed feasible.

---

## Decision 3: Claude Enterprise API Connectivity from GitHub Actions

**Decision**: Use GitHub-hosted runners (standard `ubuntu-latest`) for MVP. GitHub-hosted runners have unrestricted outbound internet access and can reach `api.anthropic.com` without VPN.

**Rationale**: The VPN risk in the original plan applies only if the organization routes GitHub Actions through a corporate proxy or uses self-hosted runners inside a firewall. GitHub's cloud-hosted runners have normal internet egress — they do not go through the corporate VPN. Claude Enterprise API is a public HTTPS endpoint; no VPN is needed.

**If self-hosted runners are required later**:
- Add `api.anthropic.com` to the egress allowlist on the runner's network
- Or configure a private LLM gateway that proxies to Anthropic

**Risk mitigation**: Validate connectivity with a `curl https://api.anthropic.com/health` step in the workflow before running agents.

**Resolved**: No VPN blocker for MVP using GitHub-hosted runners.

---

## Decision 4: Agent-to-Agent Communication Pattern

**Decision**: Sequential function calls in Python — each agent is a Python function that accepts a structured dict and returns a structured dict. The Orchestrator calls each agent in sequence, passing the cumulative context forward.

**Rationale**: Simplest possible inter-agent pattern for MVP. No message queue, no async coordination. Since agents run overnight without latency requirements, sequential blocking calls are appropriate. JSON dicts as the exchange format are readable, loggable, and easily extensible.

**Alternatives considered**:
- Async/parallel execution: Adds complexity; agents have sequential dependencies (Research → GCP → Obsidian)
- Message queue (SQS, Pub/Sub): Overkill for MVP; single GitHub Actions job is sufficient

**Resolved**: Sequential Python function calls, JSON dicts for context passing.

---

## Decision 5: Token Cost Estimates (MVP Baseline)

**Decision**: Use Sonnet 4.6 for Orchestrator only; Haiku 4.5 for all subagents.

**Estimated cost per typical overnight task run**:
| Agent | Model | Est. Tokens (in+out) | Est. Cost |
|-------|-------|----------------------|-----------|
| Orchestrator | Sonnet 4.6 | ~4,000 | ~$0.08 |
| Research Agent | Haiku 4.5 | ~3,000 | ~$0.006 |
| Obsidian Agent | Haiku 4.5 | ~5,000 | ~$0.010 |
| Total per run | — | ~12,000 | ~$0.10 |

**Rationale**: Even 20 task runs/month stays under $3. Vault caching (using existing knowledge notes instead of API calls) will reduce this further as the vault grows.

**Resolved**: Cost is not a blocker. Logging per-agent tokens enables optimization over time.

---

## Decision 6: SharePoint Vault Path

**Open item**: The exact SharePoint site URL and document library path must be confirmed by the operator before the Power Automate flow can be configured.

**What is needed**: `https://<tenant>.sharepoint.com/sites/<site>/Shared Documents/<vault-folder>/`

**Impact if unresolved**: Power Automate flow cannot be finalized. Operator must provide this path before implementing FR-12/FR-13.

**Action**: Operator to confirm SharePoint path during infrastructure setup (not a blocker for coding the Python agents or GitHub Actions workflow skeleton).

---

## Decision 7: Obsidian Vault Sync Mechanism

**Decision**: Rely on OneDrive native sync. Files written to SharePoint by Power Automate appear in the local OneDrive-synced folder, which is the Obsidian vault root.

**Rationale**: This is the existing sync path for the operator's vault. No additional tooling needed. Write latency is typically under 60 seconds for small markdown files.

**Constraint**: Obsidian must be pointed at the OneDrive-synced folder (not iCloud or local-only). Assumed to already be the case.

**Resolved**: No additional infrastructure needed.
