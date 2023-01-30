from odoo import models, api, _
import datetime


class SubscriptionPackage(models.Model):
    _inherit = 'subscription.package'

    def button_sale_order(self):
        this_products_line = []
        for rec in self.product_line_ids:
            rec_list = [0, 0, {'product_id': rec.product_id.id,
                               'product_uom_qty': rec.product_qty,
                               'analytic_account_id': rec.analytic_account_id.id,
                               'price_unit': rec.unit_price,}]
            this_products_line.append(rec_list)
        orders = self.env['sale.order'].search([('subscription_id', '=', self.id), ('invoice_status', '=', 'no')])
        if orders:
            for order in orders:
                order.action_confirm()
        so_id = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,   
            'partner_invoice_id': self.partner_id.id,
            'partner_shipping_id': self.partner_id.id,
            'partner': self.sale_order.partner.id,
            'date_of_issue': datetime.datetime.today(),
            'is_subscription': True,
            'subscription_id': self.id,
            'order_line': this_products_line
        })
        self.sale_order = so_id
        return {
            'name': _('Sales Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'domain': [('id', '=', so_id.id)],
            'view_mode': 'tree,form'
        }