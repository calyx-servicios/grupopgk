# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    is_reminder_template = fields.Boolean(
        string='Es Plantilla de Recordatorio',
        default=False,
        help='Marque esta casilla si esta plantilla se utilizará para recordatorios de facturas vencidas'
    )
    company_ids = fields.Many2many(
        'res.company',
        'mail_template_company_rel',
        'template_id',
        'company_id',
        string='Compañías',
        help='Compañías para las cuales esta plantilla estará disponible. Si no se especifica ninguna, estará disponible para todas las compañías.'
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
