from odoo import api, models

import wdb

class SaleOrder(models.Model):
    _inherit = 'sale.order'


    def _prepare_subscription_lines(self, split_line):
        values = []
        for lines in split_line:
            if not lines.product_id.is_dues_ok:
                if not lines.order_line_id.subscription_plan_id.limit_choice == 'custom':
                    price = lines.order_id.set_amount(lines) 
                else:
                    price = lines.order_id.set_amount(lines) / lines.order_line_id.subscription_plan_id.limit_count
                values.append(((0, False, {
                    'product_id': lines.product_id.id,
                    'analytic_account_id': lines.analytic_account_id.id,
                    'product_qty': lines.quantity,
                    'product_uom_id': lines.uom_id.id,
                    'unit_price': price,
                })))
        return values

    # def _create_invoices(self, grouped=False, final=False, date=None):
    #     for rec in self:
            
    #     moves = super(SaleOrder, self)._create_invoices(grouped, final, date)
    #     for move in moves:
    #         for line in move.invoice_line_ids:
    #             if not line.sale_line_ids.order_id.split_invoice:
    #                 if line.sale_line_ids.subscription_plan_id.limit_choice == 'custom' and not line.product_id.is_dues_ok:
    #                     new_price = line.price_unit / line.sale_line_ids.subscription_plan_id.limit_count
    #                     line.write({
    #                         'price_unit': new_price,
    #                     })
    #     wdb.set_trace()
    #     return moves


    def _invoice_values_line(self, split_line):
        lines = []
        for line in split_line:
            if not lines.product_id.is_dues_ok:
                if not lines.order_line_id.subscription_plan_id.limit_choice == 'custom':
                    price = lines.order_id.set_amount(lines) 
                else:
                    price = lines.order_id.set_amount(lines) / lines.order_line_id.subscription_plan_id.limit_count
                vals = {
                    'display_type': line.order_line_id.display_type,
                    'sequence': line.order_line_id.sequence,
                    'name': line.name,
                    'product_id': line.product_id.id,
                    'product_uom_id': line.uom_id.id,
                    'quantity': line.quantity,
                    'discount': line.order_line_id.discount,
                    'analytic_account_id': line.analytic_account_id.id,
                    'price_unit': price,
                    'tax_ids': [(6,0,line.tax_id.ids)],
                    'sale_line_ids': [(4, line.order_line_id.id)],
                }
                lines.append((0,0, vals))
        return lines


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"


    def _prepare_values_product(self):
        values = []
        for line in self:
            if not line.product_id.is_dues_ok:
                if not line.subscription_plan_id.limit_choice == 'custom':
                    price = line.price_unit
                else:
                    price = line.price_unit / line.subscription_plan_id.limit_count
                values.append((0, False, {
                    'product_id': line.product_id.id,
                    'analytic_account_id': line.analytic_account_id.id,
                    'product_qty': line.product_uom_qty,
                    'product_uom_id': line.product_uom.id,
                    'unit_price': price,
                }))
        return values
    
    def _prepare_invoice_line(self, **optional_values):
        self.ensure_one()
        if not self.product_id.is_dues_ok:
            if not self.subscription_plan_id.limit_choice == 'custom':
                price = self.price_unit
            else:
                price = self.price_unit / self.subscription_plan_id.limit_count
        else:
            price = self.price_unit
        res = {
            'display_type': self.display_type,
            'sequence': self.sequence,
            'name': self.name,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom.id,
            'quantity': self.qty_to_invoice,
            'discount': self.discount,
            'price_unit': price,
            'tax_ids': [(6, 0, self.tax_id.ids)],
            'sale_line_ids': [(4, self.id)],
        }
        if self.order_id.analytic_account_id and not self.display_type:
            res['analytic_account_id'] = self.order_id.analytic_account_id.id
        if self.analytic_tag_ids and not self.display_type:
            res['analytic_tag_ids'] = [(6, 0, self.analytic_tag_ids.ids)]
        if optional_values:
            res.update(optional_values)
        if self.display_type:
            res['account_id'] = False
        return res