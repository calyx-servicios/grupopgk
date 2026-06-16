# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models


class SignOcaRequest(models.Model):
    _inherit = "sign.oca.request"

    def action_send(self, sign_now=False, message=""):
        self.ensure_one()
        if self.state != "draft":
            return
        self._set_action_log("validate")
        self.state = "sent"

        send_notification = (
            not self.template_id or self.template_id.send_notification
        )
        template = self.env.ref("sign_oca_custom.mail_template_sign_request")

        for signer in self.signer_ids:
            signer._portal_ensure_token()
            if sign_now and signer.partner_id == self.env.user.partner_id:
                continue
            if send_notification:
                self._send_signer_notification(template, signer, message)

    def _send_signer_notification(self, template, signer, message):
        self.ensure_one()
        subject = _("New document to sign")
        template.with_context(
            sign_body=message,
            sign_link=signer.get_portal_url(),
            sign_subject=subject,
        ).send_mail(
            self.id,
            force_send=True,
            email_values={"recipient_ids": [(4, signer.partner_id.id)]},
            notif_layout="mail.mail_notification_light",
        )
