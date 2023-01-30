from odoo import api, models
from odoo.addons.subscription_package.models.subscription_products import SubscriptionInvoice


class AccountMove(models.Model):
    _inherit = "account.move"


    @api.model_create_multi
    def create(self, vals_list):
        for rec in vals_list:
            so_id = self.env['sale.order'].search(
                [('name', '=', rec.get('invoice_origin'))])
            if so_id.is_subscription is True:
                new_vals_list = [{'is_subscription': True,
                                  'subscription_id': so_id.subscription_id.id}]
                vals_list[0].update(new_vals_list[0])
        return super(SubscriptionInvoice, self).create(vals_list)