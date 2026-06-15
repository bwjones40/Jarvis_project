import os
import unittest
from unittest.mock import patch

from orchestrator.utils.anthropic_smoke import run_anthropic_smoke_test


class _FakeUsage:
    input_tokens = 8
    output_tokens = 3


class _FakeTextBlock:
    text = "Hello."


class _FakeMessage:
    usage = _FakeUsage()
    content = [_FakeTextBlock()]


class _FakeMessages:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeMessage()


class _FakeClient:
    def __init__(self) -> None:
        self.messages = _FakeMessages()


class AnthropicSmokeTests(unittest.TestCase):
    def test_smoke_test_calls_claude_and_returns_token_usage(self) -> None:
        client = _FakeClient()

        result = run_anthropic_smoke_test(
            model="claude-haiku-4-5",
            prompt="hello",
            client_factory=lambda: client,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["model"], "claude-haiku-4-5")
        self.assertEqual(result["response_text"], "Hello.")
        self.assertEqual(result["input_tokens"], 8)
        self.assertEqual(result["output_tokens"], 3)
        self.assertEqual(client.messages.calls[0]["messages"][0]["content"], "hello")

    def test_smoke_test_fails_fast_when_api_key_is_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = run_anthropic_smoke_test(client_factory=None)

        self.assertFalse(result["ok"])
        self.assertIn("ANTHROPIC_API_KEY is not set", result["error"])


if __name__ == "__main__":
    unittest.main()
