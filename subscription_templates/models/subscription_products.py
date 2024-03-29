from odoo import models, fields


class SubscriptionProduct(models.Model):
    _inherit = "product.template"

    subscription_plan_id = fields.Many2many('subscription.package.plan',
                                           string='Subscription Plan')
    is_dues_ok = fields.Boolean('Is Dues?', default=False)
