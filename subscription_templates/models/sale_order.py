from odoo import api, models, fields, _

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"


    @api.onchange('product_id')
    def _onchange_product_id_domain(self):
        for rec in self:
            if len(rec.product_id.subscription_plan_id.ids) == 1:
                print(f'Total: {rec.product_id.subscription_plan_id.ids}')
                rec.subscription_plan_id = rec.product_id.subscription_plan_id.id
            return {'domain': {'subscription_plan_id': [('id', 'in', rec.product_id.subscription_plan_id.ids)]}}

    subscription_plan_id = fields.Many2one('subscription.package.plan', string='Subscription Plan')
    is_subscription = fields.Boolean(compute='_compute_total_plans', string='Is subscription?')

    @api.depends('product_id')
    def _compute_total_plans(self):
        for rec in self:
            rec.is_subscription = rec.product_id.is_subscription