import json
import unittest
from unittest.mock import Mock, patch

from orchestrator.agents.gcp_discovery import _resolve_bq_executable, run_gcp_discovery


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

    def test_dataset_listing_uses_bq_project_id_flag(self) -> None:
        task_result = {
            "task": {"request": "Find GCP data", "mode": "daytime"},
            "agents_executed": [],
            "output_summary": "",
            "status": "completed",
        }
        dataset_response = Mock(
            returncode=0,
            stdout=json.dumps([{"datasetReference": {"projectId": "analytics", "datasetId": "sandbox"}}]),
            stderr="",
        )
        table_response = Mock(returncode=0, stdout=json.dumps([]), stderr="")

        with patch(
            "orchestrator.agents.gcp_discovery.subprocess.run",
            side_effect=[dataset_response, table_response],
        ) as run_mock:
            run_gcp_discovery(task_result, {"gcp": {"project": "analytics"}})

        self.assertIn("--project_id=analytics", run_mock.call_args_list[0].args[0])
        self.assertNotIn("--project=analytics", run_mock.call_args_list[0].args[0])

    def test_bq_executable_resolves_windows_command_shim(self) -> None:
        with patch("orchestrator.agents.gcp_discovery.shutil.which") as which_mock:
            which_mock.side_effect = lambda candidate: "C:/Google/Cloud SDK/google-cloud-sdk/bin/bq.cmd" if candidate == "bq.cmd" else None

            executable = _resolve_bq_executable()

        self.assertEqual(executable, "C:/Google/Cloud SDK/google-cloud-sdk/bin/bq.cmd")

    def test_schema_lookup_failure_does_not_fail_entire_discovery(self) -> None:
        task_result = {
            "task": {"request": "List BigQuery datasets", "mode": "daytime"},
            "agents_executed": [],
            "output_summary": "",
            "status": "completed",
        }
        dataset_response = Mock(
            returncode=0,
            stdout=json.dumps([{"datasetReference": {"projectId": "analytics", "datasetId": "sandbox"}}]),
            stderr="",
        )
        table_response = Mock(
            returncode=0,
            stdout=json.dumps([{"tableReference": {"tableId": "CVT Month_Summary Test no CM"}}]),
            stderr="",
        )
        schema_response = Mock(returncode=1, stdout="", stderr="not found")

        with patch(
            "orchestrator.agents.gcp_discovery.subprocess.run",
            side_effect=[dataset_response, table_response, schema_response],
        ):
            result = run_gcp_discovery(task_result, {"gcp": {"project": "analytics"}})

        gcp_run = result["agents_executed"][0]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(gcp_run["errors"], [])
        self.assertIn("CVT Month_Summary Test no CM", gcp_run["output"]["plain_english_summary"])
        self.assertEqual(gcp_run["output"]["tables"][0]["description"], "Table was visible; schema metadata was not available.")

    def test_table_list_json_failure_does_not_fail_entire_discovery(self) -> None:
        task_result = {
            "task": {"request": "List BigQuery datasets", "mode": "daytime"},
            "agents_executed": [],
            "output_summary": "",
            "status": "completed",
        }
        dataset_response = Mock(
            returncode=0,
            stdout=json.dumps(
                [
                    {"datasetReference": {"projectId": "analytics", "datasetId": "readable_dataset"}},
                    {"datasetReference": {"projectId": "analytics", "datasetId": "problem_dataset"}},
                ]
            ),
            stderr="",
        )
        good_table_response = Mock(
            returncode=0,
            stdout=json.dumps([{"tableReference": {"tableId": "orders"}}]),
            stderr="",
        )
        schema_response = Mock(returncode=0, stdout=json.dumps([{"name": "id", "type": "STRING"}]), stderr="")
        bad_table_response = Mock(returncode=0, stdout="", stderr="")

        with patch(
            "orchestrator.agents.gcp_discovery.subprocess.run",
            side_effect=[dataset_response, good_table_response, schema_response, bad_table_response],
        ):
            result = run_gcp_discovery(task_result, {"gcp": {"project": "analytics"}})

        gcp_run = result["agents_executed"][0]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(gcp_run["output"]["datasets_found"], ["readable_dataset", "problem_dataset"])
        self.assertIn("readable_dataset", gcp_run["output"]["plain_english_summary"])
        self.assertIn("problem_dataset", gcp_run["output"]["plain_english_summary"])

    def test_standard_pii_mode_preserves_technical_metadata_names(self) -> None:
        task_result = {
            "task": {"request": "List BigQuery datasets", "mode": "daytime"},
            "agents_executed": [],
            "output_summary": "",
            "status": "completed",
        }
        dataset_response = Mock(
            returncode=0,
            stdout=json.dumps([{"datasetReference": {"projectId": "analytics", "datasetId": "Erin_Bercher"}}]),
            stderr="",
        )
        table_response = Mock(
            returncode=0,
            stdout=json.dumps([{"tableReference": {"tableId": "Distributor and Customer Name"}}]),
            stderr="",
        )
        schema_response = Mock(returncode=0, stdout=json.dumps([{"name": "id", "type": "STRING"}]), stderr="")

        with patch(
            "orchestrator.agents.gcp_discovery.subprocess.run",
            side_effect=[dataset_response, table_response, schema_response],
        ):
            result = run_gcp_discovery(task_result, {"gcp": {"project": "analytics"}, "pii": {"mode": "standard"}})

        summary = result["agents_executed"][0]["output"]["plain_english_summary"]
        self.assertIn("Erin_Bercher", summary)
        self.assertIn("Distributor and Customer Name", summary)

    def test_off_pii_mode_preserves_name_like_table_names(self) -> None:
        task_result = {
            "task": {"request": "List BigQuery datasets", "mode": "daytime"},
            "agents_executed": [],
            "output_summary": "",
            "status": "completed",
        }
        dataset_response = Mock(
            returncode=0,
            stdout=json.dumps([{"datasetReference": {"projectId": "analytics", "datasetId": "Erin_Bercher"}}]),
            stderr="",
        )
        table_response = Mock(
            returncode=0,
            stdout=json.dumps([{"tableReference": {"tableId": "Distributor and Customer Name"}}]),
            stderr="",
        )
        schema_response = Mock(returncode=0, stdout=json.dumps([{"name": "id", "type": "STRING"}]), stderr="")

        with patch(
            "orchestrator.agents.gcp_discovery.subprocess.run",
            side_effect=[dataset_response, table_response, schema_response],
        ):
            result = run_gcp_discovery(task_result, {"gcp": {"project": "analytics"}, "pii": {"mode": "off"}})

        summary = result["agents_executed"][0]["output"]["plain_english_summary"]
        self.assertIn("Erin_Bercher", summary)
        self.assertIn("Distributor and Customer Name", summary)
        self.assertNotIn("[REDACTED_NAME]", summary)


if __name__ == "__main__":
    unittest.main()
