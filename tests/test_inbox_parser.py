import textwrap
import unittest
from pathlib import Path
from uuid import uuid4
import shutil

from orchestrator.utils.inbox_parser import InboxParseError, parse_inbox


TEST_ROOT = Path(".tmp-tests")
TEST_ROOT.mkdir(exist_ok=True)


VALID_INBOX = textwrap.dedent(
    """\
    # Jarvis Inbox

    ## Task: Research existing pricing notes
    **Priority**: high
    **Mode**: overnight
    **Agents needed**: research, obsidian
    **Due**: next run

    ### Request
    Summarize what the vault already says about pricing.

    ### Context
    Internal planning only.

    ### Copilot handoff
    None.

    ---
    _Clear this file after each run. Jarvis archives completed tasks to jarvis/tasks/_
    """
)


TEMPLATE_INBOX = textwrap.dedent(
    """\
    # Jarvis Inbox

    ## Task: Replace this title before commit
    **Priority**: medium
    **Mode**: overnight
    **Agents needed**: orchestrator, research, obsidian
    **Due**: next run

    ### Request
    Describe the task Jarvis should complete before the next run.

    ### Context
    Optional project context, links, or non-PII background.

    ### Copilot handoff
    Optional manual handoff instructions for Copilot.

    ---
    _Clear this file after each run. Jarvis archives completed tasks to jarvis/tasks/_
    """
)


class InboxParserTests(unittest.TestCase):
    def write_inbox(self, content: str) -> Path:
        temp_dir = TEST_ROOT / f"inbox-{uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        inbox_path = temp_dir / "inbox.md"
        inbox_path.write_text(content, encoding="utf-8")
        return inbox_path

    def test_parse_valid_inbox(self) -> None:
        inbox = self.write_inbox(VALID_INBOX)

        task = parse_inbox(inbox)

        self.assertEqual(task["title"], "Research existing pricing notes")
        self.assertEqual(task["priority"], "high")
        self.assertEqual(task["mode"], "overnight")
        self.assertEqual(task["agents_needed"], ["orchestrator", "research", "obsidian"])
        self.assertEqual(task["request"], "Summarize what the vault already says about pricing.")

    def test_empty_file_returns_none(self) -> None:
        inbox = self.write_inbox("")

        task = parse_inbox(inbox)

        self.assertIsNone(task)

    def test_template_inbox_returns_none(self) -> None:
        inbox = self.write_inbox(TEMPLATE_INBOX)

        task = parse_inbox(inbox)

        self.assertIsNone(task)

    def test_missing_request_raises_human_readable_error(self) -> None:
        inbox = self.write_inbox(
            VALID_INBOX.replace("### Request\nSummarize what the vault already says about pricing.\n\n", "")
        )

        with self.assertRaisesRegex(InboxParseError, "Request section is required"):
            parse_inbox(inbox)

    def test_invalid_priority_raises_error(self) -> None:
        inbox = self.write_inbox(VALID_INBOX.replace("**Priority**: high", "**Priority**: urgent"))

        with self.assertRaisesRegex(InboxParseError, "Priority must be one of"):
            parse_inbox(inbox)

    def test_multiple_tasks_uses_first_task(self) -> None:
        inbox = self.write_inbox(
            VALID_INBOX
            + "\n## Task: Second task\n**Priority**: low\n**Mode**: daytime\n### Request\nIgnore me.\n"
        )

        task = parse_inbox(inbox)

        self.assertEqual(task["title"], "Research existing pricing notes")


if __name__ == "__main__":
    unittest.main()
