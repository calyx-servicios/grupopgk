from odoo import models, fields, api, _


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    company_id = fields.Many2many('res.company', string='Companies', required=False, readonly=True, check_company=False)
