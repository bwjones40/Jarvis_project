import io
import json
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from uuid import uuid4
import shutil

from orchestrator.main import main
from orchestrator.agents.orchestrator import run_orchestrator
from orchestrator.utils.token_logger import calculate_cost, log_agent_run


TEST_ROOT = Path(".tmp-tests")
TEST_ROOT.mkdir(exist_ok=True)


class MainAndTokenLoggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = TEST_ROOT / f"repo-{uuid4().hex}"
        self.repo_root.mkdir(parents=True, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(self.repo_root, ignore_errors=True))
        (self.repo_root / "config").mkdir()
        (self.repo_root / "jarvis").mkdir()
        (self.repo_root / "config" / "settings.yaml").write_text(
            "models:\n  orchestrator: claude-sonnet-4-6\n  subagent: claude-haiku-4-5\n",
            encoding="utf-8",
        )
        (self.repo_root / "jarvis" / "inbox.md").write_text(
            textwrap.dedent(
                """\
                # Jarvis Inbox

                ## Task: Test task
                **Priority**: medium
                **Mode**: overnight
                **Agents needed**: orchestrator, research
                **Due**: next run

                ### Request
                Print the parsed task.
                """
            ),
            encoding="utf-8",
        )

    def test_dry_run_prints_parsed_task_json(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "--dry-run",
                    "--repo-root",
                    str(self.repo_root),
                ]
            )

        self.assertEqual(exit_code, 0)
        parsed = json.loads(stdout.getvalue())
        self.assertEqual(parsed["title"], "Test task")

    def test_log_agent_run_includes_required_fields(self) -> None:
        usage = type("Usage", (), {"input_tokens": 120, "output_tokens": 45})()

        run = log_agent_run(
            agent_name="orchestrator",
            model="claude-sonnet-4-6",
            usage=usage,
            duration=1.5,
            output={"status": "ok"},
            errors=[],
        )

        self.assertEqual(run["agent_name"], "orchestrator")
        self.assertEqual(run["input_tokens"], 120)
        self.assertEqual(run["output_tokens"], 45)
        self.assertEqual(run["duration_seconds"], 1.5)

    def test_calculate_cost_uses_pricing_table(self) -> None:
        runs = [
            {
                "agent_name": "orchestrator",
                "model": "claude-sonnet-4-6",
                "input_tokens": 1_000_000,
                "output_tokens": 1_000_000,
                "duration_seconds": 1.0,
                "output": {},
                "errors": [],
            },
            {
                "agent_name": "research",
                "model": "claude-haiku-4-5",
                "input_tokens": 500_000,
                "output_tokens": 500_000,
                "duration_seconds": 1.0,
                "output": {},
                "errors": [],
            },
        ]

        cost = calculate_cost(runs)

        self.assertAlmostEqual(cost, 20.4, places=2)

    def test_orchestrator_routes_research_and_obsidian(self) -> None:
        task = {
            "title": "Test task",
            "priority": "medium",
            "mode": "overnight",
            "agents_needed": ["orchestrator", "research", "obsidian"],
            "due": "next run",
            "request": "Summarize the vault context for Jarvis.",
            "context": "",
            "copilot_handoff": "",
        }
        settings = {
            "models": {"orchestrator": "claude-sonnet-4-6", "subagent": "claude-haiku-4-5"},
        }

        result = run_orchestrator(task, vault_notes=[], settings=settings)

        self.assertEqual(result["task_title"], "Test task")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["routing"]["agents_to_run"], ["research", "obsidian"])
        self.assertEqual(result["agents_executed"][0]["agent_name"], "orchestrator")

    def test_orchestrator_flags_pii_without_echoing_it(self) -> None:
        task = {
            "title": "PII task",
            "priority": "high",
            "mode": "overnight",
            "agents_needed": ["orchestrator", "obsidian"],
            "due": "next run",
            "request": "Summarize the status for John Smith (jsmith@example.com).",
            "context": "",
            "copilot_handoff": "",
        }
        settings = {
            "models": {"orchestrator": "claude-sonnet-4-6", "subagent": "claude-haiku-4-5"},
        }

        result = run_orchestrator(task, vault_notes=[], settings=settings)

        self.assertEqual(result["status"], "needs_clarification")
        self.assertTrue(result["clarifications_needed"])
        joined = json.dumps(result)
        self.assertNotIn("John Smith", joined)
        self.assertNotIn("jsmith@example.com", joined)

    def test_draft_request_with_name_redacts_name_in_task_output(self) -> None:
        task = {
            "title": "PII guard validation",
            "priority": "high",
            "mode": "overnight",
            "agents_needed": ["orchestrator", "research", "obsidian"],
            "due": "next run",
            "request": "Summarize the project status for John Smith (jsmith@example.com) from the Aprilia team.",
            "context": "",
            "copilot_handoff": "",
        }
        settings = {
            "models": {"orchestrator": "claude-sonnet-4-6", "subagent": "claude-haiku-4-5"},
        }

        result = run_orchestrator(task, vault_notes=[], settings=settings)

        self.assertEqual(result["status"], "needs_clarification")
        self.assertNotIn("John Smith", result["task"]["request"])
        self.assertNotIn("jsmith@example.com", result["task"]["request"])


if __name__ == "__main__":
    unittest.main()
