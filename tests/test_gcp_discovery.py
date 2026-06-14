import json
import unittest
from unittest.mock import Mock, patch

from orchestrator.agents.gcp_discovery import run_gcp_discovery


class GcpDiscoveryTests(unittest.TestCase):
    def test_daytime_discovery_summarizes_datasets_without_schema_details(self) -> None:
        task_result = {
            "task": {
                "request": "List all BigQuery datasets in the non-prod environment",
                "mode": "daytime",
            },
            "agents_executed": [],
            "output_summary": "",
            "status": "completed",
        }
        dataset_response = Mock(
            returncode=0,
            stdout=json.dumps(
                [
                    {"datasetReference": {"projectId": "analytics", "datasetId": "nonprod_finance"}},
                    {"datasetReference": {"projectId": "analytics", "datasetId": "nonprod_procurement"}},
                ]
            ),
            stderr="",
        )
        table_response = Mock(
            returncode=0,
            stdout=json.dumps(
                [
                    {"tableReference": {"tableId": "supplier_spend"}},
                    {"tableReference": {"tableId": "purchase_orders"}},
                ]
            ),
            stderr="",
        )
        schema_response = Mock(
            returncode=0,
            stdout=json.dumps(
                [
                    {"name": "supplier_name", "type": "STRING"},
                    {"name": "amount", "type": "NUMERIC"},
                ]
            ),
            stderr="",
        )

        with patch(
            "orchestrator.agents.gcp_discovery.subprocess.run",
            side_effect=[
                dataset_response,
                table_response,
                schema_response,
                schema_response,
                table_response,
                schema_response,
                schema_response,
            ],
        ):
            result = run_gcp_discovery(task_result, {"gcp": {"project": "analytics"}})

        output = result["agents_executed"][0]["output"]
        summary = output["plain_english_summary"]
        self.assertIn("nonprod_finance", summary)
        self.assertIn("supplier_spend", summary)
        self.assertNotIn("supplier_name", summary)
        self.assertNotIn('"type"', summary)
        self.assertIn("gcp_discovery", result["agents_executed"][0]["agent_name"])

    def test_overnight_mode_skips_gcp_without_bq_calls(self) -> None:
        task_result = {
            "task": {"request": "Find GCP data", "mode": "overnight"},
            "agents_executed": [],
            "output_summary": "",
            "status": "completed",
        }

        with patch("orchestrator.agents.gcp_discovery.subprocess.run") as run_mock:
            result = run_gcp_discovery(task_result, {"gcp": {"project": "analytics"}})

        self.assertEqual(run_mock.call_count, 0)
        output = result["agents_executed"][0]["output"]
        self.assertIn("GCP agent skipped: overnight mode, service account not provisioned", output["plain_english_summary"])
        self.assertEqual(result["status"], "partial")


if __name__ == "__main__":
    unittest.main()
