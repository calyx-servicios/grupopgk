from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account',
        index=True, store=True, check_company=False, readonly=False, copy=True)

    def _prepare_invoice_line(self, **optional_values):
        res = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)
        if self.analytic_account_id:
            res['analytic_account_id'] = self.analytic_account_id.id
        return res