from odoo import fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    show_on_sale_order = fields.Boolean('Show on Sale Order Lines', default=False)