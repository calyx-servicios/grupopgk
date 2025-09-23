# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class OverdueReminderStart(models.TransientModel):
    _inherit = 'overdue.reminder.start'

    def run(self):
        self.ensure_one()
        if self.company_id:
            template = self.env['mail.template'].search([
                ('is_reminder_template', '=', True),
                '|',
                ('company_ids', '=', False),
                ('company_ids', 'in', [self.company_id.id])
            ], limit=1)
            
            if not template:
                raise UserError(_(
                    "No hay plantillas de recordatorio disponibles para la compañía '%s'. "
                    "Por favor, cree una plantilla de recordatorio o asigne una a esta compañía "
                    "antes de continuar con los recordatorios de facturas vencidas."
                ) % self.company_id.name)
        
        return super().run()

    def _prepare_reminder_step(
        self,
        commercial_partner,
        base_domain,
        min_interval_date,
        payment_journals,
        sale_journals,
    ):
        vals = super()._prepare_reminder_step(
            commercial_partner,
            base_domain,
            min_interval_date,
            payment_journals,
            sale_journals,
        )
        
        if vals:
            template = self.env['mail.template'].search([
                ('is_reminder_template', '=', True),
                '|',
                ('company_ids', '=', False),
                ('company_ids', 'in', [self.company_id.id])
            ], limit=1)
            
            if template:
                vals['reminder_template_id'] = template.id
        return vals
