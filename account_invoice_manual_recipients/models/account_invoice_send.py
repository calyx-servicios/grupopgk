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
        """Validate recipients and force mail queue path for manual emails."""
        self.ensure_one()

        if not self.is_email:
            return super()._send_email()

        composer = self.composer_id
        use_manual_recipients = composer._use_manual_invoice_recipients()

        if use_manual_recipients:
            composer._raise_for_invalid_manual_recipients()
            # In comment mode Odoo posts on the document and can notify followers.
            # For manual recipients we force mass_mail so email_to is honored.
            if composer.composition_mode != "mass_mail":
                composer.composition_mode = "mass_mail"

        composer.with_context(
            no_new_invoice=True,
            mail_notify_author=(
                self.env.user.partner_id in composer.partner_ids
                and not use_manual_recipients
            ),
            mailing_document_based=True,
        )._action_send_mail()

        if self.env.context.get("mark_invoice_as_sent"):
            self.mapped("invoice_ids").sudo().write({"is_move_sent": True})

        return None
