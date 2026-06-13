# Jarvis MVP Verification Guide

This guide walks through the MVP verification process step by step so each section can be marked complete with evidence.

Use this after the code is in place and before treating Jarvis as ready for daily use.

---

## Verification Goal

Confirm that:

1. The GitHub Actions workflow triggers correctly.
2. Jarvis can parse and process inbox tasks.
3. Power Automate can write vault files successfully.
4. Draft communication safety rules are enforced.
5. PII handling rules are enforced.
6. The nightly digest path works.

---

## Before You Start

Complete these setup checks first.

- Repository is connected to GitHub.
- GitHub Actions is enabled for the repository.
- `ANTHROPIC_API_KEY` secret exists in GitHub Actions secrets.
- `POWER_AUTOMATE_WEBHOOK_URL` secret exists in GitHub Actions secrets.
- The Power Automate flow is created and enabled.
- OneDrive sync is active for the Obsidian vault.
- The SharePoint site and document library are configured in Power Automate.
- The local Obsidian vault already contains the `jarvis/` folder structure.

Record evidence:

- Screenshot of GitHub secrets page showing secret names only.
- Screenshot of Power Automate flow enabled state.
- Screenshot of local `jarvis/` folder in Obsidian or File Explorer.

---

## Section 1: Confirm Repo and Workflow Setup

### Step 1.1

Open the repository and confirm these files exist:

- `.github/workflows/jarvis.yml`
- `jarvis/inbox.md`
- `config/settings.yaml`
- `orchestrator/main.py`
- `requirements.txt`

### Step 1.2

Open `.github/workflows/jarvis.yml` and confirm:

- It triggers on push to `jarvis/inbox.md`
- It has a nightly schedule
- It installs Python 3.12
- It runs `python orchestrator/main.py`
- It includes the Anthropic connectivity check
- It includes the Power Automate smoke test step

### Pass Criteria

- All required files exist.
- Workflow includes all expected trigger and run steps.

Record evidence:

- Screenshot of repository file tree.
- Screenshot of relevant `jarvis.yml` sections.

---

## Section 2: Validate Power Automate Before Full Jarvis Run

Do this early. If this fails, later sections are blocked.

### Step 2.1

Open the Power Automate flow and confirm:

- Trigger is `When an HTTP request is received`
- The flow loops through the `files` array
- The flow creates or updates files in SharePoint
- The flow responds with HTTP 200

### Step 2.2

Manually POST a test payload to the Power Automate webhook.

Use this payload:

```json
{
  "operation": "write_file",
  "files": [
    {
      "vault_path": "jarvis/test.md",
      "content": "# PA Test\n\nThis file was written by Power Automate."
    }
  ],
  "run_metadata": {
    "task_id": "test",
    "run_timestamp": "2026-06-13T00:00:00Z",
    "total_files": 1
  }
}
```

### Step 2.3

Wait up to 60 seconds and check:

- SharePoint contains `jarvis/test.md`
- OneDrive sync completes
- Local Obsidian vault shows `jarvis/test.md`
- File content matches the payload

### Pass Criteria

- File appears in SharePoint within 30 seconds.
- File appears locally within 60 seconds.
- Content matches exactly.

Record evidence:

- Screenshot of successful Power Automate run history.
- Screenshot of `jarvis/test.md` in SharePoint.
- Screenshot of `jarvis/test.md` in Obsidian.

---

## Section 3: Validate Primary Overnight Flow

This is the main MVP test.

### Step 3.1

Edit `jarvis/inbox.md` to this:

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

### Step 3.2

Commit and push the change to the branch used by the workflow.

### Step 3.3

Open GitHub Actions and confirm the `jarvis` workflow started.

### Step 3.4

Wait for the workflow to finish, then verify:

- Workflow status is green
- A task file exists in `jarvis/tasks/`
- A digest file exists in `jarvis/digests/`
- `jarvis/inbox.md` was cleared back to template content
- The task file includes a token usage table

### Step 3.5

Open the task file and confirm:

- Title matches the test task
- Status is reasonable for the request
- Output section is not empty
- Token Usage section exists
- Draft Communications section exists, even if it says none

### Pass Criteria

- Workflow completes successfully.
- Task file exists and is readable.
- Digest file exists for the correct date.
- Inbox was cleared.
- Token table is present.

Record evidence:

- Screenshot of green GitHub Actions run.
- Screenshot of created task file.
- Screenshot of created digest file.
- Screenshot of cleared inbox file after run.

---

## Section 4: Validate Draft Communication Safety

This confirms the no-auto-send requirement is enforced.

### Step 4.1

Edit `jarvis/inbox.md` to this:

```markdown
# Jarvis Inbox

## Task: Draft Teams message
**Priority**: low
**Mode**: overnight
**Agents needed**: orchestrator, obsidian
**Due**: next run

### Request
Draft a Teams message to the Aprilia team summarizing that the work is complete
and they can request follow-up help at any time.
```

### Step 4.2

Commit and push the change.

### Step 4.3

After the workflow finishes, open the task file and digest.

Check the task file for:

- `## Draft Communications`
- A draft body
- `[HUMAN APPROVAL REQUIRED]` before the body

### Step 4.4

Confirm no external message was actually sent.

Check:

- Teams has no new outbound message from Jarvis
- No email was sent
- No other automation attempted outbound messaging

### Pass Criteria

- Draft exists in the vault output.
- Draft is flagged with `[HUMAN APPROVAL REQUIRED]`.
- No outbound message was sent automatically.

Record evidence:

- Screenshot of draft section in task file.
- Screenshot or note confirming no Teams or email send occurred.

---

## Section 5: Validate PII Guard

This is a compliance check and must pass before production use.

### Step 5.1

Edit `jarvis/inbox.md` to include real-looking PII in the request:

```markdown
# Jarvis Inbox

## Task: PII guard validation
**Priority**: high
**Mode**: overnight
**Agents needed**: orchestrator, research, obsidian
**Due**: next run

### Request
Summarize the project status for John Smith (jsmith@example.com) from the Aprilia team.
```

### Step 5.2

Commit and push the change.

### Step 5.3

After the workflow finishes, inspect every file written for that run:

- Task file
- Digest file
- Any lesson files
- Any knowledge note updates

### Step 5.4

Search those files for:

- `John Smith`
- `jsmith@example.com`

### Pass Criteria

- Neither the name nor email appears in any written vault file.
- The run is either flagged for clarification or sanitized.
- No draft communication includes the email address.

Record evidence:

- Screenshot of task output showing clarification or sanitization.
- Screenshot of search results showing zero matches for the name and email.

---

## Section 6: Validate Nightly Digest with No Task

This confirms scheduled digest behavior works even without a task assignment.

### Step 6.1

Leave `jarvis/inbox.md` empty or in its cleared template state.

### Step 6.2

Wait for the nightly scheduled run, or temporarily adjust the cron for a controlled test.

### Step 6.3

After the scheduled run finishes, verify:

- A digest file exists for that date
- The digest is valid markdown
- The digest includes a no-task message such as `No tasks assigned today`

### Pass Criteria

- Digest file is created on schedule.
- Digest is readable and correctly reflects no task activity.

Record evidence:

- Screenshot of scheduled GitHub Actions run.
- Screenshot of digest file content.

---

## Section 7: Final Sign-Off Checklist

Mark each item complete only after evidence is collected.

- [ ] Section 1 complete: Repo and workflow setup verified
- [ ] Section 2 complete: Power Automate file-write path verified
- [ ] Section 3 complete: Primary overnight flow verified
- [ ] Section 4 complete: Draft communication safety verified
- [ ] Section 5 complete: PII guard verified
- [ ] Section 6 complete: Nightly digest cron behavior verified

---

## Recommended Evidence Folder

Store screenshots and notes in one place for review.

Suggested structure:

```text
verification-evidence/
  section-1-workflow-setup/
  section-2-power-automate/
  section-3-primary-flow/
  section-4-draft-safety/
  section-5-pii-guard/
  section-6-nightly-digest/
```

---

## Handoff Prompt for Claude

If you want Claude to turn this into an HTML guide, give it this file and say:

> Convert this markdown verification guide into a clean, easy-to-follow HTML checklist with section cards, pass/fail criteria, and places to paste screenshots or notes.
