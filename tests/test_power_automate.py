import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4
import shutil

import requests

from orchestrator.utils.power_automate import post_files


TEST_ROOT = Path(".tmp-tests")
TEST_ROOT.mkdir(exist_ok=True)


class PowerAutomateTests(unittest.TestCase):
    def test_success_returns_true(self) -> None:
        response = Mock(status_code=200)
        with patch("orchestrator.utils.power_automate.requests.post", return_value=response) as post_mock:
            result = post_files(
                files=[{"vault_path": "jarvis/test.md", "content": "# Test"}],
                run_metadata={"task_id": "task-001-test", "run_timestamp": "2026-06-13T00:00:00Z", "total_files": 1},
                webhook_url="https://example.test/webhook",
            )

        self.assertTrue(result)
        self.assertEqual(post_mock.call_count, 1)

    def test_retries_on_throttled_response(self) -> None:
        retry_response = Mock(status_code=429)
        success_response = Mock(status_code=200)
        with patch(
            "orchestrator.utils.power_automate.requests.post",
            side_effect=[retry_response, success_response],
        ) as post_mock, patch("orchestrator.utils.power_automate.time.sleep") as sleep_mock:
            result = post_files(
                files=[{"vault_path": "jarvis/test.md", "content": "# Test"}],
                run_metadata={"task_id": "task-001-test", "run_timestamp": "2026-06-13T00:00:00Z", "total_files": 1},
                webhook_url="https://example.test/webhook",
            )

        self.assertTrue(result)
        self.assertEqual(post_mock.call_count, 2)
        sleep_mock.assert_called_once_with(30)

    def test_failures_write_run_errors_log(self) -> None:
        temp_dir = TEST_ROOT / f"power-automate-{uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        log_path = temp_dir / "jarvis" / "run-errors.log"
        response = Mock(status_code=500, text="server error")
        with patch("orchestrator.utils.power_automate.requests.post", return_value=response), patch(
            "orchestrator.utils.power_automate.time.sleep"
        ):
            result = post_files(
                files=[{"vault_path": "jarvis/test.md", "content": "# Test"}],
                run_metadata={"task_id": "task-001-test", "run_timestamp": "2026-06-13T00:00:00Z", "total_files": 1},
                webhook_url="https://example.test/webhook",
                error_log_path=log_path,
            )

        self.assertFalse(result)
        self.assertIn("server error", log_path.read_text(encoding="utf-8"))

    def test_network_errors_are_retried_and_logged_without_crashing(self) -> None:
        temp_dir = TEST_ROOT / f"power-automate-{uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        log_path = temp_dir / "jarvis" / "run-errors.log"

        with patch(
            "orchestrator.utils.power_automate.requests.post",
            side_effect=requests.RequestException("connection reset"),
        ) as post_mock, patch("orchestrator.utils.power_automate.time.sleep") as sleep_mock:
            result = post_files(
                files=[{"vault_path": "jarvis/test.md", "content": "# Test"}],
                run_metadata={"task_id": "task-001-test", "run_timestamp": "2026-06-13T00:00:00Z", "total_files": 1},
                webhook_url="https://example.test/webhook",
                error_log_path=log_path,
            )

        self.assertFalse(result)
        self.assertEqual(post_mock.call_count, 3)
        self.assertEqual(sleep_mock.call_count, 2)
        self.assertIn("connection reset", log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
