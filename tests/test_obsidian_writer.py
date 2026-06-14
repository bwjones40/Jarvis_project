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


if __name__ == "__main__":
    unittest.main()
