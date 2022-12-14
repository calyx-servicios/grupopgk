from odoo import api, fields, models

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account',
        index=True, store=True, compute='_compute_analytic_account_id', readonly=False, check_company=True, copy=True)

    @api.depends('product_id', 'order_id.date_order', 'order_id.partner_id')
    def _compute_analytic_account_id(self):
        for line in self:
            if not line.display_type and line.state == 'draft':
                default_analytic_account = line.env['account.analytic.default'].sudo().account_get(
                    product_id=line.product_id.id,
                    partner_id=line.order_id.partner_id.id,
                    user_id=self.env.uid,
                    date=line.order_id.date_order,
                    company_id=line.company_id.id,
                )
                line.analytic_account_id = default_analytic_account.analytic_id

    def _prepare_invoice_line(self, **optional_values):
        res = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)
        if self.analytic_account_id:
            res['analytic_account_id'] = self.analytic_account_id
        return res