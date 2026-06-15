import unittest

from orchestrator.utils.pii_guard import contains_pii, get_pii_mode, sanitize_text


class PiiGuardTests(unittest.TestCase):
    def test_strict_mode_redacts_names_and_emails(self) -> None:
        text = "John Smith owns jsmith@example.com"

        self.assertTrue(contains_pii(text, mode="strict"))
        self.assertEqual(sanitize_text(text, mode="strict"), "[REDACTED_NAME] owns [REDACTED_EMAIL]")

    def test_standard_mode_redacts_emails_but_allows_names(self) -> None:
        text = "John Smith owns jsmith@example.com"

        self.assertTrue(contains_pii(text, mode="standard"))
        self.assertEqual(sanitize_text(text, mode="standard"), "John Smith owns [REDACTED_EMAIL]")

    def test_off_mode_does_not_redact_or_flag(self) -> None:
        text = "John Smith owns jsmith@example.com"

        self.assertFalse(contains_pii(text, mode="off"))
        self.assertEqual(sanitize_text(text, mode="off"), text)

    def test_invalid_config_mode_falls_back_to_strict(self) -> None:
        self.assertEqual(get_pii_mode({"pii": {"mode": "not-a-mode"}}), "strict")

    def test_strict_mode_allows_phase_6_validation_terms(self) -> None:
        text = "Confirming Token Usage should call the Claude API through Jarvis."

        self.assertFalse(contains_pii(text, mode="strict"))
        self.assertEqual(sanitize_text(text, mode="strict"), text)


if __name__ == "__main__":
    unittest.main()
