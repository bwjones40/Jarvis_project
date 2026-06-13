"""Power Automate webhook client."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests


def post_files(
    files: list[dict[str, str]],
    run_metadata: dict[str, Any],
    webhook_url: str,
    *,
    error_log_path: str | Path = "jarvis/run-errors.log",
    timeout_seconds: int = 30,
) -> bool:
    payload = {
        "operation": "write_file",
        "files": files,
        "run_metadata": run_metadata,
    }
    retryable_statuses = {429, 500, 502, 503, 504}
    last_error = ""

    for attempt in range(1, 4):
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout_seconds,
        )
        if response.status_code == 200:
            return True

        last_error = f"Attempt {attempt} failed with status {response.status_code}: {response.text}"
        if response.status_code not in retryable_statuses or attempt == 3:
            break
        time.sleep(30)

    _write_error_log(error_log_path, payload, last_error)
    return False


def _write_error_log(error_log_path: str | Path, payload: dict[str, Any], message: str) -> None:
    path = Path(error_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "message": message,
        "payload": payload,
    }
    path.write_text(json.dumps(entry, indent=2), encoding="utf-8")
