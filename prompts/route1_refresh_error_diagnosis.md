# Route 1 Prompt: Refresh Error Diagnosis

Project: AI_Delegator
Route: `refresh-error-diagnosis`
Permission tier: `autonomous` for reads and draft generation; `confirm_before` for vault writes or dictionary updates.

## Purpose

Diagnose Power BI semantic model refresh failures from local Power BI REST API audit output. The agent should produce a plain-English explanation, ranked likely root cause, concrete remediation steps, and a delegation log entry draft.

## Required Input

At least one of:

- Workspace name
- Workspace ID
- Dataset / semantic model name

Optional but helpful:

- Known failure date or refresh window
- Recent stakeholder complaint text
- Existing `refresh_audit.py` CSV/XLSX output path

If workspace and dataset are both missing, stop and ask for the missing input.

## Local Tools

- `C:\Users\jonesbrade\Projects\pbi-automation-toolkit\scripts\refresh_audit.py`
- Power BI REST API through `MicrosoftPowerBIMgmt` or the toolkit's existing `auth.py`
- AIOps vault delegation log at `delegation-log.md` after human approval

Do not use `Connect-AzAccount`, `Az.Accounts`, FabricPS, FabricTools, or bare `Invoke-ASCmd`.

## Workflow

1. Run or read `refresh_audit.py` output for the requested workspace or dataset.
2. Exclude any row where `Skip Diagnosis = True`.
3. List skipped rows separately as decommission candidates.
4. For active failed rows, inspect:
   - `Last Refresh Status`
   - `Last Refresh Time`
   - `Service Exception JSON`
   - `Data Source Types`
   - `Source Servers`
   - `Source Databases`
   - `Gateway IDs`
   - `Owner / Configured By`
5. Pattern-match the refresh error.
6. Produce the Route 1 report.
7. Draft, but do not write, a delegation log entry unless Braden approves the vault write.

## Error Pattern Mapping

| Pattern | Root Cause | Remediation |
|---|---|---|
| credential, credentials, OAuth, token, invalid connection credentials | Credentials expired or rotated | Update data source credentials in Power BI Service under semantic model settings, then trigger a manual refresh. |
| gateway, offline, unreachable, unavailable | Gateway offline or unreachable | Check gateway machine/service status and restart or rebind the gateway as needed. |
| not found, table, view, object, 404 | Source table/view changed or was dropped | Compare the M-query source object against the current source schema and update the semantic model or source view. |
| permission, forbidden, unauthorized, access denied, 403 | Source permission revoked | Re-grant the service account or configured identity access to the source system. |
| timeout, timed out, exceeded, cancelled | Source query or model refresh timeout | Check source query performance and consider incremental refresh or query optimization. |
| billing project, quota, project, PUW, migration | Mid-migration billing project issue | Check `billing_project_api_scan.py` output. If `needs_migration = Yes`, coordinate with data engineering before changing the model. |

If no pattern matches, classify as `Unknown` and quote only the shortest relevant error excerpt from `Service Exception JSON`.

## Output Format

```markdown
## Refresh Audit Report - [Workspace Name] - [YYYY-MM-DD]

### Decommission Candidates ([N] datasets - skipped for diagnosis)

These datasets have no scheduled refresh or have not refreshed in over 18 months.
No diagnosis performed. Recommend reviewing ownership and deciding to archive or remove.

| Dataset | Last Refresh | Refresh Scheduled | Owner | Reason |
|---|---|---|---|---|
| [name] | [date or Never] | Yes/No | [owner] | [No scheduled refresh/Stale] |

### Active Datasets With Errors ([N] datasets)

#### [Dataset Name]

**Error:** [plain-English one-sentence explanation]

**Root Cause (most likely):** [pattern match result]

**Remediation Steps:**
1. [First action - who does it, where]
2. [Second action]
3. [Verification step - how to confirm it is fixed]

**Data Source Details:**
- Type: [BigQuery / Gateway / etc.]
- Server/Database: [from audit]
- Gateway ID: [if applicable]
- Last successful refresh: [date/time if available]
- Owner on record: [configured by field]

### Active Datasets - No Errors ([N] datasets)

[Dataset names or concise summary]
```

## Delegation Log Draft

Prepare this entry and ask for approval before writing it to the vault:

```markdown
## YYYY-MM-DD HH:mm - refresh-error-diagnosis - [Task Name]

- Project: AI_Delegator
- Task ID: AI-DELEGATOR-YYYYMMDD-HHMM-[slug]
- Route: refresh-error-diagnosis
- Request: [one-line description]
- Input artifact: [workspace, dataset, or audit output path]
- Tool/Agent: refresh_audit.py + Codex
- Permission tier: autonomous
- Starting status: in_progress
- Final status: ready_for_review
- Actions taken:
  - [read/extract/diagnose steps]
- Output locations:
  - [report location or conversation output]
- Review result: ready_for_review
- Time spent by AI: [minutes]
- Time spent by human review: 0
- Time saved estimate: [minutes]
- What went wrong: [none or concise failure note]
- Pattern noted: [reusable learning or prompt improvement]
- Follow-up needed: [none or next action]
```
