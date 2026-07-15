from typing import List, Tuple

from odoo import _, fields, models, tools
from odoo.exceptions import ValidationError


class MailComposeMessage(models.TransientModel):
    """Add manual recipient handling for invoice send wizard."""

    _inherit = "mail.compose.message"

    manual_recipient_emails = fields.Text(
        string="Destinatarios manuales",
        help=(
            "Ingresa una o varias direcciones de correo separadas por comas "
            "o punto y coma."
        ),
    )

    def _use_manual_invoice_recipients(self) -> bool:
        """Return True when manual recipients must drive invoice delivery."""
        self.ensure_one()
        return self.model == "account.move" and bool(self.manual_recipient_emails)

    def _split_manual_recipient_tokens(self) -> List[str]:
        """Split manual recipient input into clean candidate tokens."""
        self.ensure_one()
        raw_value = self.manual_recipient_emails or ""
        separator_normalized = raw_value.replace(";", ",")
        return [
            token.strip()
            for token in separator_normalized.split(",")
            if token and token.strip()
        ]

    def _validated_manual_recipient_emails(self) -> Tuple[List[str], List[str]]:
        """Return normalized valid emails and invalid tokens preserving order."""
        self.ensure_one()
        valid_emails: List[str] = []
        invalid_tokens: List[str] = []
        seen = set()

        for token in self._split_manual_recipient_tokens():
            normalized_email = tools.email_normalize(token)
            if not normalized_email:
                invalid_tokens.append(token)
                continue

            normalized_key = normalized_email.lower()
            if normalized_key not in seen:
                valid_emails.append(normalized_email)
                seen.add(normalized_key)

        return valid_emails, invalid_tokens

    def _raise_for_invalid_manual_recipients(self) -> None:
        """Raise a validation error when any manual email is invalid."""
        self.ensure_one()
        valid_emails, invalid_tokens = self._validated_manual_recipient_emails()
        if invalid_tokens:
            invalid_display = ", ".join(invalid_tokens)
            raise ValidationError(
                _(
                    "Formato de correo invalido en: %(emails)s",
                    emails=invalid_display,
                )
            )

        if not valid_emails:
            raise ValidationError(
                _("Ingresa al menos una direccion de correo valida.")
            )

    def get_mail_values(self, res_ids):
        """Inject manual recipients into outgoing invoice emails."""
        self.ensure_one()
        mail_values = super().get_mail_values(res_ids)

        if not self._use_manual_invoice_recipients():
            return mail_values

        self._raise_for_invalid_manual_recipients()
        valid_emails, _invalid_tokens = self._validated_manual_recipient_emails()
        email_to_value = ",".join(valid_emails)

        for res_id in res_ids:
            values = mail_values.get(res_id) or {}
            values["email_to"] = email_to_value
            # Ensure manual emails are used without partner recipient linkage.
            values["partner_ids"] = []
            values["recipient_ids"] = []
            mail_values[res_id] = values

        return mail_values
