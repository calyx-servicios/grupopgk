# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError


class OverdueReminderStep(models.TransientModel):
    _inherit = 'overdue.reminder.step'

    reminder_template_id = fields.Many2one(
        'mail.template',
        string='Plantilla de Recordatorio',
        domain="[('is_reminder_template', '=', True), '|', ('company_ids', '=', False), ('company_ids', 'in', [company_id])]",
        help='Seleccione la plantilla de correo que se utilizará para este recordatorio'
    )
    mail_body = fields.Html(
        related='reminder_template_id.body_html',
        string='Cuerpo del Correo',
        readonly=False,
        store=True
    )

    @api.onchange('company_id', 'reminder_type')
    def _onchange_company_reminder_type(self):
        """
        Actualizar automáticamente la plantilla cuando cambie la compañía o el tipo de recordatorio
        """
        if self.company_id and self.reminder_type == 'mail':
            template = self.env['mail.template'].search([
                ('is_reminder_template', '=', True),
                '|',
                ('company_ids', '=', False),
                ('company_ids', 'in', [self.env.company.id])
            ], limit=1)
            
            if template:
                self.reminder_template_id = template
            else:
                self.reminder_template_id = False

    @api.model
    def create(self, vals):
        """
        Sobrescribir create para manejar selección automática en modo masivo
        """
        record = super().create(vals)
        return record

    @api.onchange('reminder_template_id')
    def _onchange_reminder_template(self):
        """
        Actualizar el asunto y cuerpo del correo cuando cambie la plantilla
        """
        if self.reminder_template_id:
            try:
                template_lang = self.reminder_template_id.with_context(
                    lang=self.commercial_partner_id.lang or 'en_US'
                )
                
                if template_lang.subject:
                    mail_subject = template_lang._render_template(
                        template_lang.subject, self._name, [self.id]
                    )[self.id]
                    self.mail_subject = mail_subject                
            except Exception as e:
                pass

    def _get_overdue_invoice_reminder_template(self):
        """
        Sobrescribir el método para usar la plantilla seleccionada
        """
        if self.reminder_template_id:
            external_id = self.reminder_template_id.get_external_id().get(self.reminder_template_id.id)
            if external_id:
                return external_id
            else:
                return super()._get_overdue_invoice_reminder_template()
        else:
            return super()._get_overdue_invoice_reminder_template()

    def generate_mail_vals(self):
        """
        Sobrescribir el método para usar la plantilla seleccionada
        """
        self.ensure_one()
        if self.reminder_type == 'mail' and not self.reminder_template_id:
            raise UserError(_("Debe seleccionar una plantilla de recordatorio para continuar."))
        
        if self.reminder_template_id:
            mvals = self.reminder_template_id.generate_email(
                self.id, ["email_from", "email_to", "partner_to", "reply_to"]
            )
        else:
            xmlid = self._get_overdue_invoice_reminder_template()
            mvals = self.env.ref(xmlid).generate_email(
                self.id, ["email_from", "email_to", "partner_to", "reply_to"]
            )
        
        cc_list = [p.email for p in self.mail_cc_partner_ids if p.email]
        if mvals.get("email_cc"):
            cc_list.append(mvals["email_cc"])
        
        mvals.update({
            "subject": self.mail_subject,
            "body_html": self.mail_body,
            "email_cc": ", ".join(cc_list),
            "model": "res.partner",
            "res_id": self.commercial_partner_id.id,
        })
        
        mvals.pop("attachment_ids", None)
        mvals.pop("attachments", None)
        
        mail = self.env["mail.mail"].create(mvals)
        
        inv_report = self.env["ir.actions.report"]._get_report_from_name(
            "account.report_invoice_with_payments"
        )
        
        if self.company_id.overdue_reminder_attach_invoice:
            attachment_ids = self._get_attachment_ids(inv_report, mail)
            mail.write({"attachment_ids": [(6, 0, attachment_ids)]})
        
        vals = {"mail_id": mail.id}
        return vals

    def check_available_templates(self):
        """
        Verificar si hay plantillas disponibles para la compañía actual
        """
        self.ensure_one()
        if self.reminder_type == 'mail':
            template = self.env['mail.template'].search([
                ('is_reminder_template', '=', True),
                '|',
                ('company_ids', '=', False),
                ('company_ids', 'in', [self.env.company.id])
            ], limit=1)
            
            if not template:
                raise UserError(_(
                    "No hay plantillas de recordatorio disponibles para la compañía '%s'. "
                    "Por favor, cree una plantilla de recordatorio o asigne una a esta compañía."
                ) % self.env.company.name)
        return True

    def validate(self):
        for rec in self:
            rec.check_available_templates()
        return super().validate()
