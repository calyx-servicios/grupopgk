from odoo.tests.common import TransactionCase


class TestManualRecipientParser(TransactionCase):
    """Validate parsing and format checks for manual invoice recipients."""

    def test_split_and_validate_manual_recipients(self):
        """Accept comma/semicolon separated recipients and deduplicate."""
        composer = self.env["mail.compose.message"].create(
            {
                "model": "account.move",
                "manual_recipient_emails": (
                    "first@example.com; second@example.com, FIRST@example.com"
                ),
            }
        )

        valid, invalid = composer._validated_manual_recipient_emails()

        self.assertEqual(valid, ["first@example.com", "second@example.com"])
        self.assertEqual(invalid, [])

    def test_detect_invalid_manual_recipient(self):
        """Return invalid tokens when one or more emails are malformed."""
        composer = self.env["mail.compose.message"].create(
            {
                "model": "account.move",
                "manual_recipient_emails": "ok@example.com, invalid-address",
            }
        )

        valid, invalid = composer._validated_manual_recipient_emails()

        self.assertEqual(valid, ["ok@example.com"])
        self.assertEqual(invalid, ["invalid-address"])
