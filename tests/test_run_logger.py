import json
import shutil
import unittest
import warnings
from pathlib import Path
from uuid import uuid4

from orchestrator.utils.run_logger import RunContext, finalize_run, log_agent_entry, start_run


TEST_ROOT = Path(".tmp-tests")
TEST_ROOT.mkdir(exist_ok=True)


class RunLoggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TEST_ROOT / f"run-logger-{uuid4().hex}"
        self.temp_dir.mkdir(parents=True, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.original_cwd = Path.cwd()
        self.addCleanup(lambda: __import__("os").chdir(self.original_cwd))
        __import__("os").chdir(self.temp_dir)

    def test_start_run_creates_valid_json(self) -> None:
        run_ctx = start_run("jarvis", "local", task_id="task-123")

        self.assertTrue(run_ctx.log_path.exists())
        payload = json.loads(run_ctx.log_path.read_text(encoding="utf-8"))
        self.assertIn("run", payload)
        self.assertIn("agents", payload)
        self.assertEqual(payload["run"]["task_id"], "task-123")

    def test_log_agent_entry_appends(self) -> None:
        run_ctx = start_run("jarvis", "local")

        log_agent_entry(run_ctx, {"agent_name": "orchestrator"})
        log_agent_entry(run_ctx, {"agent_name": "research"})

        payload = json.loads(run_ctx.log_path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["agents"]), 2)

    def test_finalize_run_sets_status(self) -> None:
        run_ctx = start_run("jarvis", "local")

        finalize_run(run_ctx, "completed")

        payload = json.loads(run_ctx.log_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["run"]["overall_status"], "completed")
        self.assertIsNotNone(payload["run"]["completed_at"])

    def test_log_agent_entry_handles_missing_file(self) -> None:
        run_ctx = RunContext(run_id="run", trace_id="trace", log_path=self.temp_dir / "missing.json")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            log_agent_entry(run_ctx, {"agent_name": "orchestrator"})

        self.assertTrue(caught)


if __name__ == "__main__":
    unittest.main()
