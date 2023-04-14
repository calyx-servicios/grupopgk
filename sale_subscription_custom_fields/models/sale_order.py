from odoo import  models, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _prepare_subscription(self, plan, split_line):
        res = super(SaleOrder, self)._prepare_subscription(plan, split_line)
        res['payment_term_id'] = self.payment_term_id.id
        return res

    def _prepare_subscription_data(self, plan):
        res = super(SaleOrder, self)._prepare_subscription_data(plan)
        res['payment_term_id'] = self.payment_term_id.id
        return res

    def _prepare_subscription_lines(self, split_line):
        values = []
        for lines in split_line:
            if not lines.product_id.is_dues_ok:
                price = lines.order_id.set_amount(lines)
                values.append(((0, False, {
                    'sequence': lines.sequence,
                    'product_id': lines.product_id.id,
                    'name_product': lines.product_id.name,
                    'analytic_account_id': lines.analytic_account_id.id,
                    'product_qty': lines.quantity,
                    'product_uom_id': lines.uom_id.id,
                    'unit_price': price,
                    'tax_id': [(6, 0, lines.tax_id.ids)],
                    'display_type': lines.display_type,
                })))
        return values

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    
    
    def _prepare_values_product(self):
        values = []
        for line in self:
            if not line.product_id.is_dues_ok:
                price = line.price_unit
                values.append((0, False, {
                    'sequence': line.sequence,
                    'product_id': line.product_id.id,
                    'name_product': line.product_id.name,
                    'analytic_account_id': line.analytic_account_id.id,
                    'product_qty': line.product_uom_qty,
                    'product_uom_id': line.product_uom.id,
                    'unit_price': price,
                    'tax_id': [(6, 0, line.tax_id.ids)],
                    'display_type': line.display_type,
                }))
        return values