# Quickstart Validation Guide: Jarvis MVP

**Created**: 2026-06-13
**Purpose**: Runnable end-to-end scenarios to confirm the feature works before going live

---

## Prerequisites

Before running any scenario, confirm:

- [ ] GitHub repository created with `jarvis/inbox.md` file present
- [ ] GitHub Actions secret `ANTHROPIC_API_KEY` set
- [ ] GitHub Actions secret `POWER_AUTOMATE_WEBHOOK_URL` set
- [ ] Power Automate flow deployed and tested (see Scenario 3)
- [ ] Obsidian vault folder `jarvis/` initialized with empty subdirectories
- [ ] OneDrive sync confirmed active on the vault root folder

---

## Scenario 1: Overnight Task Execution (Primary Flow)

**What this validates**: FR-01 through FR-09, FR-19, Success Criterion 1

### Steps

1. Edit `jarvis/inbox.md` with a test task:
   ```markdown
   # Jarvis Inbox

   ## Task: Test overnight run
   **Priority**: low
   **Mode**: overnight
   **Agents needed**: orchestrator, research, obsidian
   **Due**: next run

   ### Request
   Summarize what you know about the Jarvis system from the vault.
   Write a brief paragraph in plain English.
   ```

2. Commit and push the file to the `main` branch.

3. Go to the GitHub Actions tab and confirm the `jarvis.yml` workflow triggered.

4. Wait for the workflow to complete (expected: under 5 minutes for this simple task).

5. Open Obsidian and verify:
   - `jarvis/tasks/task-001-test-overnight-run.md` exists and contains the output summary
   - `jarvis/digests/{today's date}.md` exists and mentions the task
   - `jarvis/inbox.md` is cleared (contains only the template footer)
   - Token usage table is populated in the task file

### Pass Criteria

- Workflow completes with green status
- Task file exists with non-empty output
- Digest file exists with date matching today
- Inbox file is cleared

---

## Scenario 2: Draft Communication Staging (Safety Check)

**What this validates**: FR-18, Success Criterion 3

### Steps

1. Edit `jarvis/inbox.md` with a task that explicitly asks for a draft message:
   ```markdown
   ## Task: Draft Teams message
   **Priority**: low
   **Mode**: overnight
   **Agents needed**: orchestrator, obsidian
   **Due**: next run

   ### Request
   Draft a Teams message to the Aprilia team summarizing that the GCP dataset
   discovery is complete and they can request a query at any time.
   ```

2. Commit and push.

3. After workflow completes, open the task file and digest.

### Pass Criteria

- Task file contains a section labeled `## Draft Communications`
- The draft message body is present
- The text `[HUMAN APPROVAL REQUIRED]` appears before the draft body
- No evidence of any message sent (check Teams; no message should appear)

---

## Scenario 3: Power Automate Webhook (Output Pipeline)

**What this validates**: FR-12, FR-13, the full output pipeline

### Steps (configure PA flow first)

1. In Power Automate, create a new flow:
   - Trigger: "When an HTTP request is received" (no authentication required)
   - Copy the generated webhook URL
   - Add action: "Create file" (SharePoint connector)
     - Site: your SharePoint vault site
     - Library: `Documents` (or your Obsidian library)
     - Folder path: `@{triggerBody()?['files'][0]['vault_path']}`... (use Apply to each)
   - Save and enable the flow

2. Test the webhook manually with curl:
   ```bash
   curl -X POST "{POWER_AUTOMATE_WEBHOOK_URL}" \
     -H "Content-Type: application/json" \
     -d '{"operation":"write_file","files":[{"vault_path":"jarvis/test.md","content":"# PA Test\n\nThis file was written by Power Automate."}],"run_metadata":{"task_id":"test","run_timestamp":"2026-06-13T00:00:00Z","total_files":1}}'
   ```

3. Wait up to 60 seconds and check:
   - SharePoint library contains `jarvis/test.md`
   - Local Obsidian shows `jarvis/test.md` in the vault

### Pass Criteria

- File appears in SharePoint within 30 seconds of the POST
- File appears in local Obsidian vault within 60 seconds via OneDrive sync
- File content matches what was sent

---

## Scenario 4: GCP Discovery (Daytime Run)

**What this validates**: FR-14 through FR-16

**Prerequisite**: Operator has active `gcloud auth` session on the machine running the agent

### Steps

1. Trigger the GCP Discovery Agent manually (daytime mode) with a test query:
   ```
   python orchestrator/main.py --task "List all BigQuery datasets in the non-prod environment"
   ```

2. Review the output:
   - Should contain dataset names and table counts
   - Should be in plain English with no raw SQL or schema syntax

### Pass Criteria

- Output lists at least one dataset by name
- No raw SQL queries appear in the output
- Output is readable without BigQuery knowledge
- No data was modified (verify with read-only audit: `bq ls` equivalent)

---

## Scenario 5: Nightly Digest (Cron Trigger)

**What this validates**: FR-04, FR-13, Success Criterion 2

### Steps

1. Confirm the GitHub Actions cron schedule is configured for 11 PM (or adjust to 5 minutes from now for testing).

2. Wait for the scheduled trigger to fire.

3. Check:
   - `jarvis/digests/{today's date}.md` exists even if no task was assigned that day
   - Digest contains a "No tasks assigned" note or lists the day's tasks

### Pass Criteria

- Digest file created on schedule
- Digest file is valid markdown and readable in Obsidian

---

## Scenario 6: PII Guard (Compliance)

**What this validates**: FR-17, Success Criterion 7

Run this scenario with `config/settings.yaml` set to `pii.mode: strict`.

### Steps

1. Assign a task that includes a real person's name and email in the request:
   ```
   ### Request
   Summarize the project status for John Smith (jsmith@example.com) from the Aprilia team.
   ```

2. After the run, check all vault files written during the task.

### Pass Criteria

- Neither `John Smith` nor `jsmith@example.com` appears in any vault file
- Task output refers to the person generically (e.g., "Aprilia team contact") or the run flags a PII warning
- If the agent wrote a draft communication, it does not contain the email address

---

## References

- Inbox file contract: [contracts/inbox-schema.md](contracts/inbox-schema.md)
- Task result schema: [contracts/task-result-schema.md](contracts/task-result-schema.md)
- Webhook payload contract: [contracts/webhook-payload.md](contracts/webhook-payload.md)
- Data model: [data-model.md](data-model.md)
