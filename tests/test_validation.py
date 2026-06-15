import io
import shutil
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from orchestrator.agents import validation as validation_agent
from orchestrator.main import main


TEST_ROOT = Path(".tmp-tests")
TEST_ROOT.mkdir(exist_ok=True)


class ValidationAgentTests(unittest.TestCase):
    def test_composite_score_formula(self) -> None:
        thresholds = {"pass_threshold": 0.90, "retry_min_threshold": 0.60}
        response = Mock()
        response.content = [type("Block", (), {"text": '{"relevance": 1.0, "completeness": 0.8, "actionability": 0.6, "format_adherence": 0.5, "notes": ""}'})()]
        client = Mock()
        client.messages.create.return_value = response

        with patch.object(validation_agent, "client", client):
            result = validation_agent.score_output("research", {"summary": "ok"}, {"task": "x"}, "run-1", thresholds)

        self.assertAlmostEqual(result.confidence_score, 0.79, places=4)

    def test_threshold_tiers(self) -> None:
        thresholds = {"pass_threshold": 0.90, "retry_min_threshold": 0.60}

        high = validation_agent._synthetic_result(0.95, thresholds)
        mid = validation_agent._synthetic_result(0.75, thresholds)
        low = validation_agent._synthetic_result(0.45, thresholds)

        self.assertTrue(high.pass_)
        self.assertTrue(mid.retry_recommended)
        self.assertTrue(low.escalate)

    def test_synthetic_pass_on_crash(self) -> None:
        thresholds = {"pass_threshold": 0.90, "retry_min_threshold": 0.60}
        client = Mock()
        client.messages.create.side_effect = Exception("boom")

        with patch.object(validation_agent, "client", client):
            result = validation_agent.score_output("research", {"summary": "ok"}, {"task": "x"}, "run-1", thresholds)

        self.assertEqual(result.confidence_score, 0.90)

    def test_override_score_env_var(self) -> None:
        thresholds = {"pass_threshold": 0.90, "retry_min_threshold": 0.60}

        with patch.dict("os.environ", {"JARVIS_VALIDATION_OVERRIDE_SCORE": "0.45"}):
            result = validation_agent.score_output("research", {"summary": "ok"}, {"task": "x"}, "run-1", thresholds)

        self.assertTrue(result.escalate)

    def test_validation_not_called_for_gcp_discovery(self) -> None:
        repo_root = TEST_ROOT / f"validation-main-{uuid4().hex}"
        repo_root.mkdir(parents=True, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(repo_root, ignore_errors=True))
        (repo_root / "config").mkdir()
        (repo_root / "jarvis").mkdir()
        (repo_root / "config" / "settings.yaml").write_text(
            textwrap.dedent(
                """\
                models:
                  orchestrator: claude-sonnet-4-6
                  subagent: claude-haiku-4-5
                validation:
                  pass_threshold: 0.90
                  retry_min_threshold: 0.60
                  retry_accept_threshold: 0.80
                  skip_threshold: 0.60
                """
            ),
            encoding="utf-8",
        )

        stdout = io.StringIO()

        def fake_gcp(task_result, settings):
            task_result["agents_executed"].append(
                {
                    "agent_name": "gcp_discovery",
                    "model": "claude-haiku-4-5",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "duration_seconds": 0.1,
                    "output": {"plain_english_summary": "ok"},
                    "errors": [],
                }
            )
            return task_result

        def fake_outputs(task_result, task, settings, vault_root="."):
            task_result["agents_executed"].append(
                {
                    "agent_name": "obsidian",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "duration_seconds": 0.1,
                    "output": {"digest_updated": "jarvis/digests/test.md", "notes_updated": []},
                    "errors": [],
                }
            )
            return [{"vault_path": "jarvis/digests/test.md", "content": "# Test"}]

        with patch("orchestrator.main.run_gcp_discovery", side_effect=fake_gcp), patch(
            "orchestrator.main.build_vault_outputs", side_effect=fake_outputs
        ), patch("orchestrator.main._maybe_post_outputs", return_value=False), patch(
            "orchestrator.main.validation_agent.score_output",
            side_effect=lambda agent_name, *args, **kwargs: validation_agent._synthetic_result(0.95, {"pass_threshold": 0.90, "retry_min_threshold": 0.60}),
        ) as score_mock, redirect_stdout(stdout):
            exit_code = main(
                [
                    "--task",
                    "List all BigQuery datasets in the non-prod environment",
                    "--repo-root",
                    str(repo_root),
                ]
            )

        self.assertEqual(exit_code, 0)
        called_agent_names = [call.args[0] for call in score_mock.call_args_list]
        self.assertNotIn("gcp_discovery", called_agent_names)


if __name__ == "__main__":
    unittest.main()
