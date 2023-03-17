from odoo import models, fields, api


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    currency_id = fields.Many2one(related="move_id.move_id.currency_id", string="Currency", readonly=True, store=False, compute_sudo=True)



