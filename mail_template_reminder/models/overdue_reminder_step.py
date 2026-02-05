# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError
import logging
import base64

_logger = logging.getLogger(__name__)


class OverdueReminderStep(models.TransientModel):
    _inherit = 'overdue.reminder.step'

    reminder_template_id = fields.Many2one(
        'mail.template',
        string='Plantilla de recordatorio',
        domain="[('is_reminder_template', '=', True), ('company_ids', 'in', [company_id])]",
        help=_('Select the email template that will be used for this reminder')
    )
    reminder_email = fields.Char(
        related='partner_id.reminder_email',
        readonly=True,
        string='Correo electrónico',
        help=_('Email address to use specifically for overdue invoice reminders. If not set, the main email will be used.')
    )
    
    invoices_data_json = fields.Text(
        string='Invoices Data JSON'
    )
    
    total_usd = fields.Float(
        string='Total USD',
        help='Total residual amount in USD'
    )
    
    total_ars = fields.Float(
        string='Total ARS',
        help='Total residual amount in ARS (Pesos)'
    )

    def _filter_invisible_lines(self, mail_body):
        """
        Filtrar y eliminar las líneas que contienen 'INVISIBLE' del body HTML
        """
        lines = mail_body.split('\n')
        filtered_lines = []
        skip_line = False
        
        for line in lines:
            if 'INVISIBLE' in line:
                skip_line = True
                continue
            if skip_line and '</tr>' in line:
                skip_line = False
                continue
            if not skip_line:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def get_invoices_from_json(self):
        """
        Obtener los datos de las facturas desde el JSON guardado
        Esto permite acceder a los residuales correctos en el onchange
        Retorna una lista: [{id, amount_residual}, ...]
        """
        if self.invoices_data_json:
            import json
            return json.loads(self.invoices_data_json)
        return []

    @api.onchange('company_id', 'reminder_type')
    def _onchange_company_reminder_type(self):
        """
        Actualizar automáticamente la plantilla cuando cambie la compañía o el tipo de recordatorio
        """
        if self.company_id and self.reminder_type == 'mail':
            template = self.env['mail.template'].search([
                ('is_reminder_template', '=', True),
                ('company_ids', 'in', [self.env.company.id])
            ], limit=1)
            
            if template:
                self.reminder_template_id = template
            else:
                self.reminder_template_id = False

    @api.model
    def create(self, vals):
        _logger.info("=== MAIL_TEMPLATE_REMINDER DEBUG ===")
        _logger.info("vals recibido: %s", vals)
        
        # Asegurar que un template se asigne antes de crear el registro
        if vals.get('reminder_type') == 'mail' and not vals.get('reminder_template_id'):
            _logger.info("Buscando template para reminder_type='mail' sin template_id")
            
            # Debug: buscar todos los templates de reminder
            all_reminder_templates = self.env['mail.template'].search([
                ('is_reminder_template', '=', True)
            ])
            _logger.info("Templates con is_reminder_template=True: %s", 
                        [f"{t.name} (ID: {t.id})" for t in all_reminder_templates])
            
            template = self.env['mail.template'].search([
                ('is_reminder_template', '=', True),
                ('company_ids', 'in', [vals.get('company_id', self.env.company.id)])
            ], limit=1)
            
            if template:
                _logger.info("Template encontrado: %s (ID: %s)", template.name, template.id)
                vals['reminder_template_id'] = template.id
            else:
                _logger.info("No se encontró template para la compañía %s", vals.get('company_id', self.env.company.id))
        
        _logger.info("vals antes de crear: %s", vals)
        
        # Crear el registro sin procesar template (saltar el create de OCA)
        step = super(models.TransientModel, self).create(vals)
        
        _logger.info("Registro creado con ID: %s", step.id)
        
        # ORDENAR LAS FACTURAS DE MÁS VIEJA A MÁS NUEVA
        if step.invoice_ids:
            # Ordenar por fecha de factura, luego por fecha de vencimiento
            sorted_invoices = step.invoice_ids.sorted(
                key=lambda inv: (inv.invoice_date or fields.Date.min, inv.invoice_date_due or fields.Date.min)
            )
            step.invoice_ids = sorted_invoices
            _logger.info("Facturas ordenadas de más vieja a más nueva")
        
        # Procesar nuestro template personalizado
        if step.reminder_template_id:
            commercial_partner = self.env["res.partner"].browse(
                vals["commercial_partner_id"]
            )
            
            # Debug: verificar las facturas
            _logger.info("=== DEBUG FACTURAS ===")
            _logger.info("step.invoice_ids: %s", step.invoice_ids)
            _logger.info("Número de facturas: %s", len(step.invoice_ids))
            
            # Guardar los datos de las facturas en JSON para usarlos en el onchange
            import json
            invoices_data = []  # Volver a usar lista como antes
            for index, inv in enumerate(step.invoice_ids):
                _logger.info("Factura [%s]: %s (ID: %s) - Fecha: %s - Saldo: %s", index, inv.name, inv.id, inv.invoice_date, inv.amount_residual)
                invoices_data.append({
                    'index': index,
                    'amount_residual': inv.amount_residual,
                })

            step.invoices_data_json = json.dumps(invoices_data)
            _logger.info("Datos de facturas guardados en JSON: %s facturas", len(invoices_data))
            
            # Calcular totales por moneda
            total_usd = 0.0
            total_ars = 0.0
            
            for inv in step.invoice_ids:
                # Ajustar el signo según el tipo de factura (refund es negativo)
                amount = inv.amount_residual * (inv.move_type == 'out_refund' and -1 or 1)
                
                # Identificar la moneda y sumar al total correspondiente
                if inv.currency_id.name == 'USD':
                    total_usd += amount
                elif inv.currency_id.name == 'PES':
                    total_ars += amount
                else:
                    # Para otras monedas, loguear para debug
                    _logger.warning("Moneda no contemplada: %s para factura %s", 
                                  inv.currency_id.name, inv.name)
            
            _logger.info("=== TOTALES POR MONEDA ===")
            _logger.info("Total USD: %s", total_usd)
            _logger.info("Total ARS: %s", total_ars)
            
            # Guardar los totales
            step.total_usd = total_usd
            step.total_ars = total_ars
            
            mail_tpl_lang = step.reminder_template_id.with_context(
                lang=commercial_partner.lang or "en_US"
            )
            mail_subject = mail_tpl_lang._render_template(
                mail_tpl_lang.subject, self._name, [step.id]
            )[step.id]
            mail_body = mail_tpl_lang._render_template(
                mail_tpl_lang.body_html, self._name, [step.id], "qweb"
            )[step.id]
            mail_body = tools.html_sanitize(mail_body)
            
            # Filtrar líneas invisibles
            mail_body = step._filter_invisible_lines(mail_body)
            
            _logger.info("=== DEBUG TEMPLATE RENDERIZADO ===")
            _logger.info("Subject renderizado: %s", mail_subject)
            _logger.info("Body renderizado (primeros 500 chars): %s", mail_body[:500])
            
            step.write(
                {
                    "mail_subject": mail_subject,
                    "mail_body": mail_body,
                }
            )
        return step

    @api.onchange('reminder_template_id')
    def _onchange_reminder_template(self):
        """
        Actualizar el asunto y cuerpo del correo cuando cambie la plantilla
        """
        if self.reminder_template_id and self.commercial_partner_id:
            try:
                # El JSON ya fue creado en create() con los residuales correctos
                # No intentar recrearlo aquí porque los residuales computados estarían en 0
                
                template_lang = self.reminder_template_id.with_context(
                    lang=self.commercial_partner_id.lang or 'en_US'
                )
                
                # Renderizar el asunto
                mail_subject = False
                if template_lang.subject:
                    mail_subject = template_lang._render_template(
                        template_lang.subject, self._name, [self.id]
                    )[self.id]
                
                # Renderizar el cuerpo del correo
                mail_body = False
                if template_lang.body_html:
                    mail_body = template_lang._render_template(
                        template_lang.body_html, self._name, [self.id], "qweb"
                    )[self.id]
                    mail_body = tools.html_sanitize(mail_body)
                    
                    # Filtrar líneas invisibles
                    mail_body = self._filter_invisible_lines(mail_body)

                # Actualizar los campos y retornar explícitamente los valores
                self.mail_subject = mail_subject
                self.mail_body = mail_body
                
                # Retornar un diccionario para forzar la actualización en la UI
                return {
                    'value': {
                        'mail_subject': mail_subject,
                        'mail_body': mail_body,
                    }
                }
                    
            except Exception as e:
                _logger.error("Error rendering template %s: %s", 
                              self.reminder_template_id.name, str(e), exc_info=True)
                return {}

    def _get_overdue_invoice_reminder_template(self):
        """
        Sobrescribir para usar nuestro template personalizado por defecto
        """
        # Si hay un reminder_template_id seleccionado, usarlo
        if self.reminder_template_id:
            external_id = self.reminder_template_id.get_external_id().get(self.reminder_template_id.id)
            if external_id:
                return external_id
        
        # Si no hay template seleccionado, usar nuestro template personalizado por defecto
        return 'mail_template_reminder.custom_overdue_invoice_reminder_mail_template'
    
    def generate_mail_vals(self):
        """
        Sobrescribir el método para usar la plantilla seleccionada
        """
        self.ensure_one()
        if self.reminder_type == 'mail' and not self.reminder_template_id:
            raise UserError(_("You must select a reminder template to continue."))
        
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
        
        inv_report = self.env.ref("invoice_without_detail.action_invoce_without_details")
        
        if self.company_id.overdue_reminder_attach_invoice:
            try:
                attachment_ids = self._get_attachment_ids(inv_report, mail)
                mail.write({"attachment_ids": [(6, 0, attachment_ids)]})
            except Exception as e:
                # Si hay error en la generación de PDFs, continuar sin adjuntos
                _logger.warning("Error generando PDFs para recordatorio %s: %s", self.id, str(e))
        
        vals = {"mail_id": mail.id}
        return vals

    def _get_attachment_ids(self, inv_report, mail):
        """
        Sobrescribir el método para manejar mejor los errores de generación de PDF
        """
        attachment_ids = []
        iao = self.env["ir.attachment"]
        problematic_invoices = []
        
        for inv in self.invoice_ids:
            try:
                if inv_report.report_type in ("qweb-html", "qweb-pdf"):
                    report_bin, report_format = inv_report._render_qweb_pdf([inv.id])
                else:
                    res = inv_report.render([inv.id])
                    if not res:
                        raise UserError(
                            _("Report format '%s' is not supported.")
                            % inv_report.report_type
                        )
                    report_bin, report_format = res
                
                filename = "{}.{}".format(inv._get_report_base_filename(), report_format)
                attach = iao.create(
                    {
                        "name": filename,
                        "datas": base64.b64encode(report_bin),
                        "res_model": "mail.message",
                        "res_id": mail.mail_message_id.id,
                    }
                )
                attachment_ids.append(attach.id)
                
            except Exception as e:
                # Si hay error con una factura específica, la marcamos como problemática
                problematic_invoices.append(inv.name or inv.id)
                _logger.warning("Error generando PDF para factura %s: %s", inv.name or inv.id, str(e))
                continue
        
        # Si hay facturas problemáticas, mostrar advertencia al usuario
        if problematic_invoices:
            _logger.warning("No se pudieron generar PDFs para las siguientes facturas: %s", 
                          ", ".join(problematic_invoices))
        
        return attachment_ids

    def check_available_templates(self):
        """
        Verificar si hay plantillas disponibles para la compañía actual
        """
        self.ensure_one()
        if self.reminder_type == 'mail':
            template = self.env['mail.template'].search([
                ('is_reminder_template', '=', True),
                ('company_ids', 'in', [self.env.company.id])
            ], limit=1)
            
            if not template:
                raise UserError(_(
                    "No reminder templates available for company '%s'. "
                    "Please create a reminder template or assign one to this company."
                ) % self.env.company.name)
        return True

    def validate(self):
        for rec in self:
            rec.check_available_templates()
        return super().validate()

    def get_invoice_safe(self, index):
        """
        Obtiene una factura de forma segura por índice
        Si el índice no existe, devuelve valores ficticios
        """
        _logger.info("get_invoice_safe(%s): len(invoice_ids) = %s", index, len(self.invoice_ids))
        
        # Usar invoice_ids directamente (ya están ordenados en create())
        if len(self.invoice_ids) > index:
            inv = self.invoice_ids[index]
            _logger.info("get_invoice_safe(%s): Retornando factura real ID=%s, name=%s", index, inv.id, inv.name)
            return inv
        else:
            _logger.warning("get_invoice_safe(%s): NO hay factura, retornando FakeInvoice", index)
            # Devolver valores ficticios para que el template no falle
            class FakeInvoice:
                def __init__(self):
                    self.id = 0
                    self.name = 'INVISIBLE'
                    self.invoice_date = ''
                    self.invoice_payment_term_id = type('obj', (object,), {'name': ''})()
                    self.invoice_date_due = ''
                    self.ref = ''
                    self.amount_untaxed = 0.0
                    self.amount_total = 0.0
                    self.amount_residual = 0.0
                    self.move_type = 'out_invoice'
                    # Crear una moneda ficticia con decimal_places y método round
                    class FakeCurrency:
                        def __init__(self):
                            self.name = 'USD'
                            self.symbol = '$'
                            self.decimal_places = 2
                            self.position = 'before'
                        
                        def round(self, amount):
                            return round(amount, self.decimal_places)
                    
                    self.currency_id = FakeCurrency()
                    self.overdue_reminder_counter = 0
            return FakeInvoice()
    
    def get_residual_by_index(self, index):
        """
        Obtiene el amount_residual desde el JSON por índice
        Este es el método recomendado para usar en templates
        """
        # Si el índice no es válido, retornar 0
        if not isinstance(index, int) or index < 0:
            return 0.0
            
        invoices_data = self.get_invoices_from_json()
        
        # Buscar por índice en la lista
        for inv_data in invoices_data:
            if inv_data.get('index') == index:
                return inv_data.get('amount_residual', 0.0)
        
        # Fallback: si no hay JSON, buscar directamente en invoice_ids
        if len(self.invoice_ids) > index:
            return self.invoice_ids[index].amount_residual
        
        return 0.0