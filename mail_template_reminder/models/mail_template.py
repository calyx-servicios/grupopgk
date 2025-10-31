# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    is_reminder_template = fields.Boolean(
        string=_('Is Reminder Template'),
        default=False,
        help=_('Check this box if this template will be used for overdue invoice reminders')
    )
    company_ids = fields.Many2many(
        'res.company',
        'mail_template_company_rel',
        'template_id',
        'company_id',
        string=_('Companies'),
        help=_('Companies for which this template will be available. If none specified, it will be available for all companies.')
    )

    @api.model
    def get_reminder_templates(self, company_id=None):
        """
        Método para obtener plantillas de recordatorio filtradas por compañía
        """
        domain = [('is_reminder_template', '=', True)]
        
        if company_id:
            domain.append('|')
            domain.append(('company_ids', '=', False))  # Sin compañías específicas (disponible para todas)
            domain.append(('company_ids', 'in', [company_id]))  # O que incluya la compañía específica
        
        return self.search(domain)
