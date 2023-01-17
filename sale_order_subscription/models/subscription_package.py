from odoo import _, api, models, fields, SUPERUSER_ID


class SubscriptionPackageProductLine(models.Model):
    _inherit = 'subscription.package.product.line'

    unit_price = fields.Float(string='Unit Price', store=True, readonly=False, related="")

    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account',
    index=True, store=True, compute='_compute_analytic_account_id', readonly=False, check_company=True, copy=True)

    @api.depends('product_id', 'subscription_id.sale_order.date_order', 'subscription_id.sale_order.partner_id')
    def _compute_analytic_account_id(self):
        for line in self:
            if line.subscription_id.stage_id == 'draft':
                default_analytic_account = line.env['account.analytic.default'].sudo().account_get(
                    product_id=line.product_id.id,
                    partner_id=line.subscription_id.sale_order.partner_id.id,
                    user_id=self.env.uid,
                    date=line.subscription_id.sale_order.date_order,
                    company_id=line.company_id.id,
                )
                line.analytic_account_id = default_analytic_account.analytic_id
