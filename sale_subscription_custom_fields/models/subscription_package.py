from odoo import api, models, fields, _
from dateutil.relativedelta import relativedelta


class SubscriptionPackageProductLine(models.Model):
    _inherit = 'subscription.package.product.line'

    tax_id = fields.Many2many('account.tax', string='Taxes', context={'active_test': False}, check_company=True)
    price_tax = fields.Float(compute='_compute_total_amount', string='Total Tax', store=True)
    price_subtotal = fields.Monetary(compute='_compute_total_amount', string='Subtotal', store=True)
    name_product = fields.Char(string='Description')


    @api.depends('product_qty', 'unit_price', 'tax_id')
    def _compute_total_amount(self):
        """
        Compute the amounts of the Subscription product line.
        """
        for line in self:
            price = line.unit_price
            taxes = line.tax_id.compute_all(price, line.currency_id, line.product_qty, product=line.product_id, partner=line.subscription_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'total_amount': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

class SubscriptionPackage(models.Model):
    _inherit = 'subscription.package'

    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term')

    def create_invoice_forced(self):
        this_products_line = []
        for rec in self.product_line_ids:
            rec_list = [0, 0, {'product_id': rec.product_id.id,
                            'name': rec.name_product,
                            'quantity': rec.product_qty,
                            'price_unit': rec.unit_price,
                            'analytic_account_id': rec.analytic_account_id.id,
                            'tax_ids': [(6, 0, rec.tax_id.ids)],

                            }]
            this_products_line.append(rec_list)
        move = self.env['account.move'].create(
            {
                'move_type': 'out_invoice',
                'date': fields.Date.today(),
                'invoice_date': fields.Date.today(),
                'state': 'draft',
                'sale_type_id': self.sale_order.type_id.id,
                'partner_id': self.partner_invoice_id.id,
                'invoice_payment_term_id': self.payment_term_id,
                'currency_id': self.partner_invoice_id.currency_id.id,
                'invoice_line_ids': this_products_line,
                'subscription_id': self.id,
                'company_id': self.company_id.id,
                'partner': self.sale_order.partner.id
            })
        if move:
            today_date = fields.Date.today()
            renewal_value = int(self.plan_id.renewal_value)
            if self.plan_id.renewal_period in ['days','weeks']:
                if self.plan_id.renewal_period == 'days':
                    self.next_invoice_date = today_date + relativedelta(
                        days=renewal_value)
                else:
                    self.next_invoice_date = today_date + relativedelta(
                        days=(renewal_value * 7))
            elif self.plan_id.renewal_period == 'months':
                self.next_invoice_date = today_date + relativedelta(
                    months=renewal_value)
            else:
                self.next_invoice_date = today_date + relativedelta(
                    years=renewal_value)
        return move