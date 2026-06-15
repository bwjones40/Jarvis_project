"""Daytime-only GCP metadata discovery agent."""

from __future__ import annotations

import json
import shutil
import subprocess
from time import perf_counter
from typing import Any

from orchestrator.utils.pii_guard import contains_pii, get_pii_mode, sanitize_text
from orchestrator.utils.token_logger import log_agent_run


SKIP_MESSAGE = "GCP agent skipped: overnight mode, service account not provisioned"


def run_gcp_discovery(task_result: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Append a read-only GCP discovery result to a TaskResult."""
    start = perf_counter()
    task = task_result.get("task", {})
    mode = task.get("mode", task_result.get("mode", "overnight"))
    pii_mode = get_pii_mode(settings)
    errors: list[str] = []

    if mode != "daytime":
        output = {
            "datasets_found": [],
            "tables": [],
            "plain_english_summary": SKIP_MESSAGE,
        }
        task_result["status"] = "partial"
        return _append_run(task_result, settings, start, output, errors)

    request = str(task.get("request", ""))
    if contains_pii(request, mode=pii_mode):
        output = {
            "datasets_found": [],
            "tables": [],
            "plain_english_summary": "GCP discovery stopped because the request contained PII.",
        }
        task_result["status"] = "needs_clarification"
        errors.append("PII detected in GCP discovery request.")
        return _append_run(task_result, settings, start, output, errors)

    project = settings.get("gcp", {}).get("project", "").strip()
    if not project:
        output = {
            "datasets_found": [],
            "tables": [],
            "plain_english_summary": "GCP discovery needs settings.gcp.project before it can run.",
        }
        task_result["status"] = "needs_clarification"
        errors.append("Missing settings.gcp.project.")
        return _append_run(task_result, settings, start, output, errors)

    try:
        datasets = _list_datasets(project)
        table_summaries = _list_table_summaries(project, datasets)
        summary = _plain_english_summary(project, datasets, table_summaries, pii_mode)
        output = {
            "datasets_found": datasets,
            "tables": table_summaries,
            "plain_english_summary": summary,
        }
        if task_result.get("status") == "completed":
            task_result["output_summary"] = summary
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
        safe_error = sanitize_text(str(exc), mode=pii_mode)
        output = {
            "datasets_found": [],
            "tables": [],
            "plain_english_summary": "GCP discovery could not complete. Check local gcloud authentication and bq CLI access.",
        }
        task_result["status"] = "partial"
        errors.append(safe_error)

    return _append_run(task_result, settings, start, output, errors)


def _list_datasets(project: str) -> list[str]:
    response = _run_bq(["bq", "ls", f"--project_id={project}", "--format=json"])
    data = json.loads(response)
    datasets: list[str] = []
    for item in data:
        reference = item.get("datasetReference", {})
        dataset_id = reference.get("datasetId")
        if dataset_id:
            datasets.append(str(dataset_id))
    return datasets


def _list_table_summaries(project: str, datasets: list[str]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for dataset in datasets:
        table_response = _run_bq(["bq", "ls", "--format=json", f"{project}:{dataset}"])
        try:
            tables = json.loads(table_response)
        except json.JSONDecodeError:
            tables = []
        for table in tables[:10]:
            table_id = str(table.get("tableReference", {}).get("tableId", "")).strip()
            if not table_id:
                continue
            description = "Schema was reachable with read-only metadata access."
            try:
                _run_bq(["bq", "show", "--schema", "--format=json", f"{project}:{dataset}.{table_id}"])
            except subprocess.SubprocessError:
                description = "Table was visible; schema metadata was not available."
            summaries.append(
                {
                    "dataset": dataset,
                    "table": table_id,
                    "description": description,
                }
            )
    return summaries


def _run_bq(command: list[str]) -> str:
    command = [_resolve_bq_executable(), *command[1:]]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise subprocess.SubprocessError(completed.stderr.strip() or f"Command failed: {' '.join(command)}")
    return completed.stdout


def _resolve_bq_executable() -> str:
    for candidate in ("bq", "bq.cmd", "bq.exe", "bq.bat"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return "bq"


def _plain_english_summary(project: str, datasets: list[str], tables: list[dict[str, Any]], pii_mode: str = "strict") -> str:
    if not datasets:
        return f"No BigQuery datasets were visible in project {project}."

    lines = [
        f"Found {len(datasets)} BigQuery dataset(s) visible in project {project}.",
        "Datasets:",
    ]
    for dataset in datasets:
        dataset_tables = [item for item in tables if item["dataset"] == dataset]
        table_names = ", ".join(item["table"] for item in dataset_tables[:5]) or "no tables visible"
        lines.append(f"- {dataset}: {len(dataset_tables)} table(s) visible. Examples: {table_names}.")
    lines.append("No data was modified; discovery used read-only metadata commands.")
    return sanitize_text("\n".join(lines), mode=pii_mode)


def _append_run(
    task_result: dict[str, Any],
    settings: dict[str, Any],
    start: float,
    output: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    usage = type("Usage", (), {"input_tokens": 0, "output_tokens": 0})()
    task_result.setdefault("agents_executed", []).append(
        log_agent_run(
            agent_name="gcp_discovery",
            model=settings.get("models", {}).get("subagent", "claude-haiku-4-5"),
            usage=usage,
            duration=perf_counter() - start,
            output=output,
            errors=errors,
        )
    )
    return task_result
