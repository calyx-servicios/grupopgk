# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class OverdueReminderStep(models.TransientModel):
    _name = 'overdue.reminder.step.temp'

    reminder_template_id = fields.Many2one(
        'mail.template',
        string='Plantilla de Recordatorio',
        domain="[('is_reminder_template', '=', True), '|', ('company_ids', '=', False), ('company_ids', 'in', [company_id])]",
        help='Seleccione la plantilla de correo que se utilizará para este recordatorio'
    )
    mail_body = fields.Html(
        string='Cuerpo del Correo',
        help='Copia del cuerpo del template seleccionado'
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
        Sobrescribir create para usar el template personalizado en lugar del hardcodeado
        """
        _logger.info(f"=== CREATE DEBUG ===")
        _logger.info(f"Vals recibidos: {vals}")
        
        # Siempre crear usando el create base, sin llamar al create del módulo OCA
        step = super(models.Model, self).create(vals)
        
        _logger.info(f"Step creado con ID: {step.id}")
        _logger.info(f"Reminder template ID: {step.reminder_template_id}")
        
        # DEBUG: Verificar invoice_ids después de crear
        _logger.info(f"=== INVOICE_IDS DEBUG ===")
        _logger.info(f"Invoice IDs en step: {step.invoice_ids}")
        _logger.info(f"Cantidad de facturas: {len(step.invoice_ids)}")
        for inv in step.invoice_ids:
            _logger.info(f"  - Factura: {inv.name}, Saldo: {inv.amount_residual}, Fecha: {inv.invoice_date}")
        
        # Después de crear, decidir qué template usar
        if step.reminder_template_id:
            _logger.info(f"Usando template personalizado: {step.reminder_template_id.name}")
            # Renderizar el template personalizado
            mail_tpl = step.reminder_template_id
            mail_tpl_lang = mail_tpl.with_context(lang=step.commercial_partner_id.lang or "en_US")
            
            try:
                _logger.info(f"Renderizando template con step.id: {step.id}")
                _logger.info(f"Template subject: {mail_tpl_lang.subject}")
                
                mail_subject = mail_tpl_lang._render_template(
                    mail_tpl_lang.subject, self._name, [step.id]
                )[step.id]
                mail_body = mail_tpl_lang._render_template(
                    mail_tpl_lang.body_html, self._name, [step.id], "qweb"
                )[step.id]
                mail_body = tools.html_sanitize(mail_body)
                
                _logger.info(f"Subject renderizado: {mail_subject[:50]}...")
                _logger.info(f"Body renderizado: {len(mail_body)} caracteres")
                
                step.write({
                    "mail_subject": mail_subject,
                    "mail_body": mail_body,
                })
                _logger.info("Template personalizado aplicado correctamente")
            except Exception as e:
                _logger.error(f"Error renderizando template personalizado: {e}")
        else:
            _logger.info("No hay template personalizado, usando comportamiento original")
        
        return step

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
                
                # NO actualizar mail_subject con contenido renderizado, mantener el template dinámico
                # if template_lang.subject:
                #     mail_subject = template_lang._render_template(
                #         template_lang.subject, self._name, [self.id]
                #     )[self.id]
                #     self.mail_subject = mail_subject
                
                # NO actualizar mail_body con contenido renderizado, mantener el template dinámico
                # if template_lang.body_html:
                #     mail_body = template_lang._render_template(
                #         template_lang.body_html, self._name, [self.id], "qweb"
                #     )[self.id]
                #     self.mail_body = tools.html_sanitize(mail_body)
                    
            except Exception as e:
                pass

    def update_template_content(self):
        """
        Método para forzar la actualización del contenido del template
        """
        self.ensure_one()
        if self.reminder_template_id:
            commercial_partner = self.commercial_partner_id
            mail_tpl = self.reminder_template_id
            mail_tpl_lang = mail_tpl.with_context(lang=commercial_partner.lang or "en_US")
            
            try:
                mail_subject = mail_tpl_lang._render_template(
                    mail_tpl_lang.subject, self._name, [self.id]
                )[self.id]
                mail_body = mail_tpl_lang._render_template(
                    mail_tpl_lang.body_html, self._name, [self.id], "qweb"
                )[self.id]
                mail_body = tools.html_sanitize(mail_body)
                
                # NO pisar mail_subject ni mail_body con contenido renderizado, mantener el template dinámico
                # self.write({
                #     "mail_subject": mail_subject,
                #     "mail_body": mail_body,
                # })
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
                # return super()._get_overdue_invoice_reminder_template()  # Comentado temporalmente
                return None
        else:
            # return super()._get_overdue_invoice_reminder_template()  # Comentado temporalmente
            return None

    def generate_mail_vals(self):
        """
        Sobrescribir el método para usar la plantilla seleccionada
        """
        self.ensure_one()
        _logger.info(f"=== GENERATE_MAIL_VALS DEBUG ===")
        _logger.info(f"Reminder template ID: {self.reminder_template_id}")
        _logger.info(f"Mail subject actual: {self.mail_subject}")
        _logger.info(f"Mail body actual: {len(self.mail_body) if self.mail_body else 0} caracteres")
        
        if self.reminder_type == 'mail' and not self.reminder_template_id:
            raise UserError(_("Debe seleccionar una plantilla de recordatorio para continuar."))
        
        if self.reminder_template_id:
            _logger.info(f"Generando email con template personalizado: {self.reminder_template_id.name}")
            mvals = self.reminder_template_id.generate_email(
                self.id, ["email_from", "email_to", "partner_to", "reply_to"]
            )
            _logger.info(f"Template personalizado generado - Subject: {mvals.get('subject', 'None')}")
        else:
            _logger.info("Generando email con template original")
            xmlid = self._get_overdue_invoice_reminder_template()
            mvals = self.env.ref(xmlid).generate_email(
                self.id, ["email_from", "email_to", "partner_to", "reply_to"]
            )
        
        cc_list = [p.email for p in self.mail_cc_partner_ids if p.email]
        if mvals.get("email_cc"):
            cc_list.append(mvals["email_cc"])
        
        # No pisar subject y body_html con valores estáticos, usar los del template renderizado
        mvals.update({
            "email_cc": ", ".join(cc_list),
            "model": "res.partner",
            "res_id": self.commercial_partner_id.id,
        })
        
        # Solo actualizar subject y body si no vienen del template
        if not mvals.get("subject") and self.mail_subject:
            mvals["subject"] = self.mail_subject
        if not mvals.get("body_html") and self.mail_body:
            mvals["body_html"] = self.mail_body
        
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
            # Asegurar que el contenido del template esté actualizado
            if rec.reminder_template_id:
                rec.update_template_content()
        # return super().validate()  # Comentado temporalmente
        return True
