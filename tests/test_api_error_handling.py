"""Regression tests: LLM agents degrade gracefully on API failure.

A bad/expired API key or an Anthropic outage must NOT halt the pipeline. The
research and obsidian_writer model calls return ``None`` on persistent failure,
which their callers treat as a graceful fallback. Auth/permission errors must
not waste a retry, since they will not clear on their own.
"""

import unittest
from unittest.mock import Mock, patch

import anthropic
import httpx

from orchestrator.agents import obsidian_writer as obsidian_agent
from orchestrator.agents import research as research_agent


def _auth_error() -> anthropic.AuthenticationError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(401, request=request)
    return anthropic.AuthenticationError("invalid x-api-key", response=response, body=None)


def _api_error() -> anthropic.APIError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIError("transient outage", request=request, body=None)


class ResearchErrorHandlingTests(unittest.TestCase):
    def test_auth_error_returns_none_without_retry(self) -> None:
        client = Mock()
        client.messages.create.side_effect = _auth_error()
        with patch.object(research_agent, "client", client):
            result = research_agent._call_research_model("hello")
        self.assertIsNone(result)
        self.assertEqual(client.messages.create.call_count, 1)  # no retry on a dead key

    def test_persistent_api_error_returns_none_after_one_retry(self) -> None:
        client = Mock()
        client.messages.create.side_effect = _api_error()
        with patch.object(research_agent, "client", client), \
                patch.object(research_agent, "sleep", lambda *_: None):
            result = research_agent._call_research_model("hello")
        self.assertIsNone(result)
        self.assertEqual(client.messages.create.call_count, 2)  # one retry, then give up


class ObsidianWriterErrorHandlingTests(unittest.TestCase):
    def test_auth_error_returns_none_without_retry(self) -> None:
        client = Mock()
        client.messages.create.side_effect = _auth_error()
        with patch.object(obsidian_agent, "client", client):
            result = obsidian_agent._call_obsidian_writer_model("hello")
        self.assertIsNone(result)
        self.assertEqual(client.messages.create.call_count, 1)

    def test_persistent_api_error_returns_none_after_one_retry(self) -> None:
        client = Mock()
        client.messages.create.side_effect = _api_error()
        with patch.object(obsidian_agent, "client", client), \
                patch.object(obsidian_agent, "sleep", lambda *_: None):
            result = obsidian_agent._call_obsidian_writer_model("hello")
        self.assertIsNone(result)
        self.assertEqual(client.messages.create.call_count, 2)


if __name__ == "__main__":
    unittest.main()
