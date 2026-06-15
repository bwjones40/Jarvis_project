"""Minimal Anthropic API smoke test for operator verification."""

from __future__ import annotations

import argparse
import os
from typing import Any, Callable


def run_anthropic_smoke_test(
    model: str = "claude-haiku-4-5",
    prompt: str = "hello",
    client_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    if client_factory is None and not os.getenv("ANTHROPIC_API_KEY", "").strip():
        return {"ok": False, "error": "ANTHROPIC_API_KEY is not set."}

    if client_factory is None:
        from anthropic import Anthropic

        client_factory = Anthropic

    try:
        client = client_factory()
        message = client.messages.create(
            model=model,
            max_tokens=16,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        return {"ok": False, "error": f"Anthropic smoke test failed: {exc}"}

    usage = getattr(message, "usage", None)
    return {
        "ok": True,
        "model": model,
        "response_text": _extract_response_text(getattr(message, "content", [])),
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
    }


def _extract_response_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for item in content or []:
        text = getattr(item, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a minimal Anthropic API smoke test.")
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--prompt", default="hello")
    args = parser.parse_args()

    result = run_anthropic_smoke_test(model=args.model, prompt=args.prompt)
    if not result["ok"]:
        print(result["error"])
        return 1
    print(
        "Anthropic smoke test succeeded: "
        f"model={result['model']} "
        f"input_tokens={result['input_tokens']} "
        f"output_tokens={result['output_tokens']} "
        f"response={result['response_text']!r}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
