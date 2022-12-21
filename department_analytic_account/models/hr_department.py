from odoo import models, fields


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    analytic_account = fields.Many2one(comodel_name='account.analytic.account', string='Analytic Account')
