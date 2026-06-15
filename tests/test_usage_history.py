import json
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from orchestrator.utils.usage_history import append_usage_history, load_usage_history


class UsageHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(".tmp-tests") / f"usage-history-{uuid4().hex}"
        self.repo_root.mkdir(parents=True, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(self.repo_root, ignore_errors=True))

    def test_append_usage_history_persists_task_usage(self) -> None:
        task_result = {
            "task_id": "task-001-history",
            "run_timestamp": "2026-06-15T00:00:00Z",
            "status": "completed",
            "agents_executed": [
                {
                    "agent_name": "orchestrator",
                    "model": "claude-sonnet-4-6",
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "duration_seconds": 1.0,
                    "output": {},
                    "errors": [],
                }
            ],
        }

        append_usage_history(self.repo_root, task_result)

        history_path = self.repo_root / "jarvis" / "usage-history.json"
        self.assertTrue(history_path.exists())
        entries = json.loads(history_path.read_text(encoding="utf-8"))
        self.assertEqual(entries[0]["task_id"], "task-001-history")
        self.assertEqual(entries[0]["input_tokens"], 100)
        self.assertEqual(load_usage_history(self.repo_root), entries)


if __name__ == "__main__":
    unittest.main()
