from odoo import models, fields, api


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    currency_id = fields.Many2one(compute="_compute_currency_id", string="Currency", readonly=True, store=True, compute_sudo=True)
    
    @api.depends('move_id')
    def _compute_currency_id(self):
        if self.move_id:
            self.currency_id = self.move_id.currency_id.id
        else:
            self.currency_id = self.company_id.currency_id.id