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

    def test_deduplicate_attachment_ids(self):
        """Keep a single attachment when duplicates have same name/content."""
        composer = self.env["mail.compose.message"].create(
            {
                "model": "account.move",
                "manual_recipient_emails": "ok@example.com",
            }
        )

        attachment_1 = self.env["ir.attachment"].create(
            {
                "name": "invoice.pdf",
                "datas": "dGVzdA==",
                "res_model": "mail.compose.message",
                "res_id": 0,
                "type": "binary",
            }
        )
        attachment_2 = self.env["ir.attachment"].create(
            {
                "name": "invoice.pdf",
                "datas": "dGVzdA==",
                "res_model": "mail.compose.message",
                "res_id": 0,
                "type": "binary",
            }
        )

        deduplicated_ids = composer._deduplicate_attachment_ids(
            [attachment_1.id, attachment_2.id]
        )

        self.assertEqual(deduplicated_ids, [attachment_1.id])

    def test_deduplicate_attachment_ids_same_content_diff_name(self):
        """Keep a single attachment when content matches but name differs."""
        composer = self.env["mail.compose.message"].create(
            {
                "model": "account.move",
                "manual_recipient_emails": "ok@example.com",
            }
        )

        attachment_1 = self.env["ir.attachment"].create(
            {
                "name": "FA-A 00012-00003282.pdf",
                "datas": "dGVzdA==",
                "res_model": "mail.compose.message",
                "res_id": 0,
                "type": "binary",
            }
        )
        attachment_2 = self.env["ir.attachment"].create(
            {
                "name": "Invoice_FA-A 00012-00003282.pdf",
                "datas": "dGVzdA==",
                "res_model": "mail.compose.message",
                "res_id": 0,
                "type": "binary",
            }
        )

        deduplicated_ids = composer._deduplicate_attachment_ids(
            [attachment_1.id, attachment_2.id]
        )

        self.assertEqual(deduplicated_ids, [attachment_1.id])

    def test_deduplicate_attachment_ids_from_link_commands(self):
        """Support m2m link commands in attachment_ids payload."""
        composer = self.env["mail.compose.message"].create(
            {
                "model": "account.move",
                "manual_recipient_emails": "ok@example.com",
            }
        )

        attachment_1 = self.env["ir.attachment"].create(
            {
                "name": "invoice.pdf",
                "datas": "dGVzdA==",
                "res_model": "mail.compose.message",
                "res_id": 0,
                "type": "binary",
            }
        )
        attachment_2 = self.env["ir.attachment"].create(
            {
                "name": "Invoice_invoice.pdf",
                "datas": "dGVzdA==",
                "res_model": "mail.compose.message",
                "res_id": 0,
                "type": "binary",
            }
        )

        deduplicated_ids = composer._deduplicate_attachment_ids(
            [(4, attachment_1.id, 0), (4, attachment_2.id, 0)]
        )

        self.assertEqual(deduplicated_ids, [attachment_1.id])

    def test_deduplicate_attachment_ids_same_name_diff_content(self):
        """Keep a single attachment when names match but content differs."""
        composer = self.env["mail.compose.message"].create(
            {
                "model": "account.move",
                "manual_recipient_emails": "ok@example.com",
            }
        )

        attachment_1 = self.env["ir.attachment"].create(
            {
                "name": "FA-A 00012-00003282.pdf",
                "datas": "dGVzdDE=",
                "res_model": "mail.compose.message",
                "res_id": 0,
                "type": "binary",
            }
        )
        attachment_2 = self.env["ir.attachment"].create(
            {
                "name": "FA-A 00012-00003282.pdf",
                "datas": "dGVzdDI=",
                "res_model": "mail.compose.message",
                "res_id": 0,
                "type": "binary",
            }
        )

        deduplicated_ids = composer._deduplicate_attachment_ids(
            [attachment_1.id, attachment_2.id]
        )

        self.assertEqual(deduplicated_ids, [attachment_1.id])
