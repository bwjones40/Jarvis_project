import json
import shutil
import unittest
import warnings
from pathlib import Path
from uuid import uuid4

from orchestrator.agents import stats_reporter


TEST_ROOT = Path(".tmp-tests")
TEST_ROOT.mkdir(exist_ok=True)


class StatsReporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TEST_ROOT / f"stats-reporter-{uuid4().hex}"
        self.logs_dir = self.temp_dir / "jarvis" / "logs"
        self.stats_dir = self.temp_dir / "jarvis" / "ci"
        self.logs_dir.mkdir(parents=True, exist_ok=False)
        self.stats_dir.mkdir(parents=True, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_first_run_scans_all_logs(self) -> None:
        self._write_log(
            "2026-06-15",
            "run-1.json",
            "2026-06-15T23:00:00Z",
            [{"agent_name": "research", "status": "success", "latency_ms": 100, "token_usage": {"total": 10, "estimated_cost_usd": 0.01}}],
        )
        self._write_log(
            "2026-06-16",
            "run-2.json",
            "2026-06-16T23:00:00Z",
            [{"agent_name": "obsidian_writer", "status": "success", "latency_ms": 200, "token_usage": {"total": 20, "estimated_cost_usd": 0.02}, "confidence_score": 0.9}],
        )

        stats_reporter.run_stats_report(str(self.logs_dir), str(self.stats_dir))

        payload = self._latest_stats_payload()
        self.assertIsNone(payload["analysis_window_start"])
        self.assertEqual(payload["total_runs_analyzed"], 2)
        self.assertEqual(payload["total_agent_executions"], 2)

    def test_window_start_from_prior_report(self) -> None:
        baseline = {
            "analysis_window_end": "2026-06-16T23:00:00Z",
        }
        (self.stats_dir / "stats_2026-06-16.json").write_text(json.dumps(baseline), encoding="utf-8")

        window_start = stats_reporter._find_window_start(str(self.stats_dir))

        self.assertEqual(window_start, "2026-06-16T23:00:00Z")

    def test_malformed_log_skipped(self) -> None:
        day_dir = self.logs_dir / "2026-06-15"
        day_dir.mkdir(parents=True, exist_ok=False)
        (day_dir / "bad.json").write_text("{not-json", encoding="utf-8")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            stats_reporter.run_stats_report(str(self.logs_dir), str(self.stats_dir))

        self.assertTrue(caught)
        payload = self._latest_stats_payload()
        self.assertEqual(payload["total_runs_analyzed"], 0)

    def test_aggregate_stats_accuracy(self) -> None:
        entries = [
            {
                "agent_name": "research",
                "status": "success",
                "latency_ms": 100,
                "token_usage": {"total": 100, "estimated_cost_usd": 0.01},
                "retry_count": 0,
                "escalation_flag": False,
                "confidence_score": 0.8,
            },
            {
                "agent_name": "research",
                "status": "partial",
                "latency_ms": 300,
                "token_usage": {"total": 300, "estimated_cost_usd": 0.03},
                "retry_count": 1,
                "escalation_flag": True,
                "confidence_score": 0.6,
            },
        ]

        rows = stats_reporter._aggregate_agent_stats(entries)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["agent_name"], "research")
        self.assertEqual(rows[0]["run_count"], 2)
        self.assertEqual(rows[0]["success_rate"], 0.5)
        self.assertEqual(rows[0]["avg_latency_ms"], 200)
        self.assertEqual(rows[0]["avg_tokens_per_run"], 200)
        self.assertEqual(rows[0]["total_cost_usd"], 0.04)
        self.assertEqual(rows[0]["retry_count"], 1)
        self.assertEqual(rows[0]["escalation_count"], 1)
        self.assertEqual(rows[0]["avg_confidence_score"], 0.7)

    def test_confidence_score_absent_for_unvalidated_agents(self) -> None:
        rows = stats_reporter._aggregate_agent_stats(
            [
                {
                    "agent_name": "gcp_discovery",
                    "status": "success",
                    "latency_ms": 100,
                    "token_usage": {"total": 0, "estimated_cost_usd": 0.0},
                }
            ]
        )

        self.assertNotIn("avg_confidence_score", rows[0])

    def _write_log(self, date_slug: str, filename: str, started_at: str, agents: list[dict]) -> None:
        day_dir = self.logs_dir / date_slug
        day_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "run": {
                "run_id": filename.replace(".json", ""),
                "trace_id": filename.replace(".json", ""),
                "workflow_id": "jarvis",
                "trigger_source": "local",
                "started_at": started_at,
                "completed_at": started_at,
                "overall_status": "completed",
            },
            "agents": agents,
        }
        (day_dir / filename).write_text(json.dumps(payload), encoding="utf-8")

    def _latest_stats_payload(self) -> dict:
        latest = sorted(self.stats_dir.glob("stats_*.json"))[-1]
        return json.loads(latest.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
