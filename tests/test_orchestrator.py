import io
import json
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from uuid import uuid4
import shutil
from unittest.mock import patch

from orchestrator.main import main
from orchestrator.agents.research import run_research
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

    def test_dry_run_reports_no_task_for_cleared_template(self) -> None:
        (self.repo_root / "jarvis" / "inbox.md").write_text(
            textwrap.dedent(
                """\
                # Jarvis Inbox

                ## Task: Replace this title before commit
                **Priority**: medium
                **Mode**: overnight
                **Agents needed**: orchestrator, research, obsidian
                **Due**: next run

                ### Request
                Describe the task Jarvis should complete before the next run.

                ### Context
                Optional project context, links, or non-PII background.

                ### Copilot handoff
                Optional manual handoff instructions for Copilot.

                ---
                _Clear this file after each run. Jarvis archives completed tasks to jarvis/tasks/_
                """
            ),
            encoding="utf-8",
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(["--dry-run", "--repo-root", str(self.repo_root)])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue().strip(), "No task in inbox")

    def test_direct_task_runs_daytime_gcp_discovery(self) -> None:
        stdout = io.StringIO()

        with patch("orchestrator.main.run_gcp_discovery") as gcp_mock, patch(
            "orchestrator.main.build_vault_outputs", return_value=[]
        ), patch("orchestrator.main._maybe_post_outputs", return_value=False), redirect_stdout(stdout):
            gcp_mock.side_effect = lambda task_result, settings: task_result
            exit_code = main(
                [
                    "--task",
                    "List all BigQuery datasets in the non-prod environment",
                    "--repo-root",
                    str(self.repo_root),
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(gcp_mock.call_count, 1)
        parsed = json.loads(stdout.getvalue())
        self.assertEqual(parsed["task"]["mode"], "daytime")
        self.assertIn("gcp", parsed["task"]["agents_needed"])

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

    def test_research_caps_cache_hit_context_to_configured_token_budget(self) -> None:
        note_dir = self.repo_root / "jarvis" / "knowledge"
        note_dir.mkdir(parents=True, exist_ok=True)
        (note_dir / "long-note.md").write_text("# Long Note\n\n" + ("longnoteunique " * 2500), encoding="utf-8")
        task_result = {
            "task": {"request": "longnoteunique", "mode": "overnight"},
            "agents_executed": [],
            "output_summary": "",
            "status": "completed",
        }

        result = run_research(
            task_result,
            {"research": {"max_context_notes": 3, "cache_hit_threshold": 0.1, "max_tokens_per_note": 100}},
            str(self.repo_root / "jarvis"),
        )

        summary = result["research_summary"]
        self.assertLessEqual(len(summary.split()), 110)
        self.assertIn("truncated", summary.lower())


if __name__ == "__main__":
    unittest.main()
