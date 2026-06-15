import unittest

from orchestrator.agents.obsidian_writer import build_vault_outputs


class ObsidianWriterTests(unittest.TestCase):
    def test_digest_generated_when_no_tasks_ran(self) -> None:
        outputs = build_vault_outputs(
            task_result=None,
            task=None,
            settings={"vault": {"digests_dir": "jarvis/digests", "tasks_dir": "jarvis/tasks", "lessons_dir": "jarvis/agents"}},
        )

        digest = next(item for item in outputs if item["vault_path"].startswith("jarvis/digests/"))
        self.assertIn("No tasks assigned today", digest["content"])

    def test_draft_communications_are_flagged(self) -> None:
        task = {
            "title": "Draft task",
            "request": "Draft a Teams update.",
        }
        task_result = {
            "task_id": "task-001-draft-task",
            "task_title": "Draft task",
            "run_timestamp": "2026-06-13T00:00:00Z",
            "mode": "overnight",
            "status": "completed",
            "agents_executed": [
                {
                    "agent_name": "orchestrator",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "duration_seconds": 0.1,
                    "output": {
                        "draft_message": "Teams message: Project complete."
                    },
                    "errors": [],
                }
            ],
            "output_summary": "Draft prepared.",
            "draft_communications": [],
            "clarifications_needed": [],
            "knowledge_updates": [],
        }

        outputs = build_vault_outputs(
            task_result=task_result,
            task=task,
            settings={"vault": {"digests_dir": "jarvis/digests", "tasks_dir": "jarvis/tasks", "lessons_dir": "jarvis/agents"}},
        )

        task_file = next(item for item in outputs if item["vault_path"] == "jarvis/tasks/task-001-draft-task.md")
        self.assertIn("[HUMAN APPROVAL REQUIRED]", task_file["content"])
        self.assertIn("## Draft Communications", task_file["content"])
        self.assertIn("Teams Draft", task_file["content"])
        self.assertIn("| obsidian | claude-haiku-4-5 |", task_file["content"])

    def test_request_for_teams_message_creates_explicit_draft(self) -> None:
        task = {
            "title": "Draft Teams message",
            "request": "Draft a Teams message to the Aprilia team summarizing that the work is complete.",
        }
        task_result = {
            "task_id": "task-001-draft-teams-message",
            "task_title": "Draft Teams message",
            "run_timestamp": "2026-06-13T00:00:00Z",
            "mode": "overnight",
            "status": "completed",
            "agents_executed": [
                {
                    "agent_name": "orchestrator",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "duration_seconds": 0.1,
                    "output": {
                        "plan": "Route to obsidian"
                    },
                    "errors": [],
                }
            ],
            "output_summary": "Task parsed and routed for execution.",
            "draft_communications": [],
            "clarifications_needed": [],
            "knowledge_updates": [],
        }

        outputs = build_vault_outputs(
            task_result=task_result,
            task=task,
            settings={"models": {"subagent": "claude-haiku-4-5"}, "vault": {"digests_dir": "jarvis/digests", "tasks_dir": "jarvis/tasks", "lessons_dir": "jarvis/agents"}},
        )

        task_file = next(item for item in outputs if item["vault_path"] == "jarvis/tasks/task-001-draft-teams-message.md")
        self.assertIn("[HUMAN APPROVAL REQUIRED]", task_file["content"])
        self.assertIn("request follow-up help at any time", task_file["content"])
        self.assertIn("## Draft Communications", task_file["content"])

    def test_pii_name_and_email_do_not_appear_in_task_file(self) -> None:
        task = {
            "title": "PII guard validation",
            "request": "Summarize the project status for John Smith (jsmith@example.com) from the Aprilia team.",
        }
        task_result = {
            "task_id": "task-001-pii-guard-validation",
            "task_title": "PII guard validation",
            "run_timestamp": "2026-06-13T00:00:00Z",
            "mode": "overnight",
            "status": "needs_clarification",
            "agents_executed": [
                {
                    "agent_name": "orchestrator",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "duration_seconds": 0.1,
                    "output": {
                        "plan": "Route to research, obsidian"
                    },
                    "errors": [],
                }
            ],
            "output_summary": "Task parsed and routed for execution.",
            "draft_communications": [],
            "clarifications_needed": ["PII detected in input. Remove names, email addresses, and customer data before rerunning."],
            "knowledge_updates": [],
            "task": {
                "title": "PII guard validation",
                "priority": "high",
                "mode": "overnight",
                "agents_needed": ["orchestrator", "research", "obsidian"],
                "due": "next run",
                "request": "Input withheld because it contained PII.",
                "context": "",
                "copilot_handoff": "",
            },
        }

        outputs = build_vault_outputs(
            task_result=task_result,
            task=task,
            settings={"models": {"subagent": "claude-haiku-4-5"}, "vault": {"digests_dir": "jarvis/digests", "tasks_dir": "jarvis/tasks", "lessons_dir": "jarvis/agents"}},
        )

        task_file = next(item for item in outputs if item["vault_path"] == "jarvis/tasks/task-001-pii-guard-validation.md")
        self.assertNotIn("John Smith", task_file["content"])
        self.assertNotIn("jsmith@example.com", task_file["content"])
        self.assertIn("[REDACTED_NAME]", task_file["content"])
        self.assertIn("[REDACTED_EMAIL]", task_file["content"])

    def test_task_record_lists_lesson_and_knowledge_outputs(self) -> None:
        task_result = {
            "task_id": "task-001-knowledge-update",
            "task_title": "Knowledge update",
            "run_timestamp": "2026-06-13T00:00:00Z",
            "mode": "overnight",
            "status": "completed",
            "agents_executed": [
                {
                    "agent_name": "orchestrator",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 1_000,
                    "output_tokens": 500,
                    "duration_seconds": 1.0,
                    "output": {"plan": "Route to obsidian"},
                    "errors": [],
                }
            ],
            "output_summary": "Updated the evergreen note.",
            "draft_communications": [],
            "clarifications_needed": [],
            "knowledge_updates": ["jarvis/knowledge/gcp/datasets.md"],
        }

        outputs = build_vault_outputs(
            task_result=task_result,
            task={"request": "Update the GCP dataset note."},
            settings={"models": {"subagent": "claude-haiku-4-5"}, "vault": {"digests_dir": "jarvis/digests", "tasks_dir": "jarvis/tasks", "lessons_dir": "jarvis/agents"}},
        )

        task_file = next(item for item in outputs if item["vault_path"] == "jarvis/tasks/task-001-knowledge-update.md")
        self.assertIn("- jarvis/agents/orchestrator-lessons.md", task_file["content"])
        self.assertIn("- jarvis/agents/obsidian-lessons.md", task_file["content"])
        self.assertIn("- jarvis/knowledge/gcp/datasets.md", task_file["content"])

    def test_digest_includes_weekly_cost_rollup_heading(self) -> None:
        task_result = {
            "task_id": "task-001-cost-rollup",
            "task_title": "Cost rollup",
            "run_timestamp": "2026-06-13T00:00:00Z",
            "mode": "overnight",
            "status": "completed",
            "agents_executed": [
                {
                    "agent_name": "orchestrator",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 1_000,
                    "output_tokens": 500,
                    "duration_seconds": 1.0,
                    "output": {},
                    "errors": [],
                }
            ],
            "output_summary": "Cost rollup produced.",
            "draft_communications": [],
            "clarifications_needed": [],
            "knowledge_updates": [],
        }

        outputs = build_vault_outputs(
            task_result=task_result,
            task={"request": "Summarize costs."},
            settings={"models": {"subagent": "claude-haiku-4-5"}, "vault": {"digests_dir": "jarvis/digests", "tasks_dir": "jarvis/tasks", "lessons_dir": "jarvis/agents"}},
        )

        digest = next(item for item in outputs if item["vault_path"].startswith("jarvis/digests/"))
        self.assertIn("## Weekly Cost Rollup", digest["content"])
        self.assertIn("Last 7 days estimated cost", digest["content"])

    def test_digest_does_not_count_clarification_runs_as_completed(self) -> None:
        task_result = {
            "task_id": "task-001-needs-clarification",
            "task_title": "Needs clarification",
            "run_timestamp": "2026-06-13T00:00:00Z",
            "mode": "overnight",
            "status": "needs_clarification",
            "agents_executed": [
                {
                    "agent_name": "orchestrator",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "duration_seconds": 0.1,
                    "output": {},
                    "errors": [],
                }
            ],
            "output_summary": "Task parsed and routed for execution.",
            "draft_communications": [],
            "clarifications_needed": ["Add missing context."],
            "knowledge_updates": [],
        }

        outputs = build_vault_outputs(
            task_result=task_result,
            task={"request": "Clarify this request."},
            settings={"models": {"subagent": "claude-haiku-4-5"}, "vault": {"digests_dir": "jarvis/digests", "tasks_dir": "jarvis/tasks", "lessons_dir": "jarvis/agents"}},
        )

        digest = next(item for item in outputs if item["vault_path"].startswith("jarvis/digests/"))
        self.assertIn("## Tasks Completed\n\n- (none)", digest["content"])
        self.assertIn("## Tasks Requiring Attention", digest["content"])
        self.assertIn("task-001-needs-clarification", digest["content"])

    def test_digest_honors_off_pii_mode(self) -> None:
        task_result = {
            "task_id": "task-001-digest-pii-off",
            "task_title": "Review John Smith datasets",
            "run_timestamp": "2026-06-13T00:00:00Z",
            "mode": "daytime",
            "status": "completed",
            "agents_executed": [
                {
                    "agent_name": "orchestrator",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "duration_seconds": 0.1,
                    "output": {},
                    "errors": [],
                }
            ],
            "output_summary": "Completed.",
            "draft_communications": [],
            "clarifications_needed": [],
            "knowledge_updates": [],
        }

        outputs = build_vault_outputs(
            task_result=task_result,
            task={"request": "Review John Smith datasets."},
            settings={
                "pii": {"mode": "off"},
                "models": {"subagent": "claude-haiku-4-5"},
                "vault": {"digests_dir": "jarvis/digests", "tasks_dir": "jarvis/tasks", "lessons_dir": "jarvis/agents"},
            },
        )

        digest = next(item for item in outputs if item["vault_path"].startswith("jarvis/digests/"))
        self.assertIn("Review John Smith datasets", digest["content"])
        self.assertNotIn("[REDACTED_NAME]", digest["content"])


if __name__ == "__main__":
    unittest.main()
