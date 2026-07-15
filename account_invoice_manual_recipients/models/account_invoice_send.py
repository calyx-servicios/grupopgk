from odoo import fields, models


class AccountInvoiceSend(models.TransientModel):
    """Validate manual recipients before launching invoice email sending."""

    _inherit = "account.invoice.send"

    manual_recipient_emails = fields.Text(
        string="Destinatarios",
        related="composer_id.manual_recipient_emails",
        readonly=False,
    )

    def _send_email(self):
        """Validate manual recipients before delegating to standard sending."""
        self.ensure_one()
        if self.is_email:
            self.composer_id._raise_for_invalid_manual_recipients()
        return super()._send_email()
